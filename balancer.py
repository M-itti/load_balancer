import itertools
import threading
import time
import yaml
import tornado.ioloop
import tornado.web
import tornado.httpclient
import requests
from abc import ABC, abstractmethod
from multiprocessing import Value, Lock

import logging_config
from logging_config import logger

# TODO: add docstring for methods

class ReverseProxy(tornado.web.RequestHandler):
    def initialize(self, server_pool, router):
        self.server_pool = server_pool
        self.router = router
        logger.debug(self.server_pool)

    async def get(self):
        # choosing the backend server to route
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
        
        # TODO: hard coded
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
        if not self.enabled:
            return

        logger.info("Performing health check")

        while True:  # Keep the health check running in a loop
            for server in self.server_pool:
                alive = self.check_server(server)
                self.server_pool[server]["alive"] = alive
            time.sleep(self.interval)  # Wait before the next health check

    def check_server(self, server):
        try:
            response = requests.get(server, timeout=self.timeout)
            if response.status_code == 200:
                logger.info(f"{server} is alive")
                return True
            else:
                logger.warning(f"{server} returned status {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            logger.warning(f"{server} is down: {e}")
            return False

class Strategy(ABC):
    @abstractmethod
    def route(self, request, server_pool):
        pass

class RoundRobin(Strategy):
    def __init__(self):
        self.index = Value('i', 0)  

    def route(self, request, server_pool):
        # Convert the keys of the server_pool dict into a list
        active_servers = [server for server, is_alive in server_pool.items() if is_alive]
        
        # Check if there are any active servers
        if not active_servers:
            raise Exception("No available servers")

        # Use the round-robin approach to select the server
        with self.index.get_lock():
            server = active_servers[self.index.value % len(active_servers)]
            self.index.value += 1

        return server

class LeastConnections(Strategy):
    def __init__(self):
        self.lock = Lock()

    def route(self, request, server_pool):
        with self.lock:
            active_servers = {server: data for server, data in server_pool.items() if data["alive"]}
            #print(active_servers)
            
            if not active_servers:
                raise Exception("No available servers")

            # Select the server with the least connections
            #server = min(active_servers, key=lambda s: active_servers[s]["connections"])
            server = min(active_servers, key=lambda s: server_pool[s]["connections"])
            
            # Increment the connection count for the selected server
            #active_servers[server]["connections"] += 1
            server_pool[server]["connections"] += 1
            print(server_pool)
        
        return server

class Router:
    def __init__(self, config, server_pool):
        self.server_pool = server_pool
        routing_config = config.get('routing', {})

        # if strategy key is emtpy, round_robin is assigned to strategy_name
        strategy_name = routing_config.get('strategy', 'round_robin')
        logger.info(f"Selected strategy: {strategy_name}")

        # select the appropriate strategy based on the config
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
