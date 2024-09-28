import itertools
import threading
import time
import yaml
import tornado.ioloop
import tornado.web
import tornado.httpclient
import requests
from abc import ABC, abstractmethod
from multiprocessing import Value, Lock, Manager

import logging_config
from logging_config import logger

class ReverseProxy(tornado.web.RequestHandler):
    def initialize(self, server_pool, router):
        self.server_pool = server_pool
        self.router = router
        logger.debug(self.server_pool)

    async def get(self):
        # Choosing the backend server to route
        url = self.router.route_request(self.request.uri)  
        response = await self.attempt_request(url)

        if response:
            self.set_status(response.code)
            for header, value in response.headers.get_all():
                self.set_header(header, value)
            self.write(response.body)
        else:
            self.send_error(502)

    async def attempt_request(self, url):
        logger.info(f"Forwarding request to: {url}")
        
        # TODO: this is hard coded
        http_client = tornado.httpclient.AsyncHTTPClient(max_clients=200)
        try:
            response = await http_client.fetch(url + self.request.uri, headers=self.request.headers)
            return response
        except tornado.httpclient.HTTPClientError as e:
            logger.error(f"Request failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Request failed: {e}")
            return None
        finally:
            # Decrement the connection count for the server
            if url in self.server_pool:
                self.server_pool[url]["connections"] -= 1

class HealthCheck:
    def __init__(self, config, server_pool):
        self.server_pool = server_pool
        self.enabled = config.get('health_check', {}).get('enabled', False)
        self.interval = config.get('health_check', {}).get('interval', 10)
        self.timeout = config.get('health_check', {}).get('timeout', 5)

    def perform_check(self):
        if self.enabled:
            logger.info("Performing health check")
            for server in list(self.server_pool.keys()):
                try:
                    response = requests.get(server, timeout=self.timeout)
                    response.raise_for_status()
                    self.server_pool[server]["alive"] = True
                    logger.info(f"{server} is alive")
                except requests.RequestException as e:
                    self.server_pool[server]["alive"] = False
                    logger.warning(f"{server} is down: {e}")

    def start(self):
        if self.enabled:
            while True:
                self.perform_check()
                time.sleep(self.interval)

class Strategy(ABC):
    @abstractmethod
    def route(self, request, server_pool):
        pass

class RoundRobin(Strategy):
    def __init__(self):
        self.index = Value('i', 0)

    def route(self, request, server_pool):
        active_servers = [server for server, data in server_pool.items() if data["alive"]]

        if not active_servers:
            raise Exception("No available servers")

        with self.index.get_lock():
            # Use the index to get the current server
            server = active_servers[self.index.value % len(active_servers)]
            # Update the index for the next call
            self.index.value = (self.index.value + 1) % len(active_servers)

        return server

class LeastConnections(Strategy):
    def __init__(self):
        self.lock = Lock()

    def route(self, request, server_pool):
        with self.lock:
            active_servers = {server: data for server, data in server_pool.items() if data["alive"]}

            if not active_servers:
                raise Exception("No available servers")

            # Select the server with the least connections
            server = min(active_servers, key=lambda s: server_pool[s]["connections"])
            server_pool[server]["connections"] += 1  # Increment the connection count

        return server

class Router:
    def __init__(self, config, server_pool):
        self.server_pool = server_pool
        routing_config = config.get('routing', {})
        strategy_name = routing_config.get('strategy', 'round_robin')
        logger.info(f"Selected strategy: {strategy_name}")
        self.strategy = self.select_strategy(strategy_name)

    def select_strategy(self, strategy_name):
        if strategy_name == 'round_robin':
            return RoundRobin()
        elif strategy_name == 'least_connections':
            return LeastConnections()
        else:
            raise ValueError(f"Unknown routing strategy: {strategy_name}")

    def route_request(self, request):
        server = self.strategy.route(request, self.server_pool)
        logger.info(f"Routing request to {server} using {self.strategy.__class__.__name__} strategy")
        return server

