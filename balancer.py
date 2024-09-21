import itertools
import threading
import time
import logging
import yaml
import tornado.ioloop
import tornado.web
import tornado.httpclient
import logging_config

logger = logging.getLogger(__name__)

# Configuration Class
class Config:
    def __init__(self, config_file):
        self.config_data = self.load_config(config_file)

    def load_config(self, config_file):
        with open(config_file, 'r') as file:
            return yaml.safe_load(file)

    def get(self, key, default=None):
        return self.config_data.get(key, default)

class ReverseProxy(tornado.web.RequestHandler):
    def initialize(self, server_pool, router):
        self.server_pool = server_pool
        self.router = router
        print(self.server_pool)

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
            self.send_error(502, 'Bad Gateway')

    async def attempt_request(self, url):
        logger.info(f"Forwarding request to: {url}")

        http_client = tornado.httpclient.AsyncHTTPClient()
        try:
            response = await http_client.fetch(url + self.request.uri, headers=self.request.headers)
            return response
        except tornado.httpclient.HTTPClientError as e:
            logger.error(f"Request failed: {e}")
            return None

# Worker Class
class Worker:
    def __init__(self, id):
        self.id = id
        self.active = True

    def start(self):
        print(f"Starting worker {self.id}")
        # Add logic to start the worker

    def stop(self):
        print(f"Stopping worker {self.id}")
        self.active = False
        # Add logic to stop the worker

# Health Check Class
class HealthCheck:
    def __init__(self, config, server_pool):
        self.server_pool = server_pool
        self.enabled = config.get('health_check', {}).get('enabled', False)
        self.interval = config.get('health_check', {}).get('interval', 10)

    async def perform_check(self):
        if self.enabled:
            logger.info("Performing health check")
            http_client = tornado.httpclient.AsyncHTTPClient()

            for server in self.server_pool:
                try:
                    # TODO: add timeout, apply retry logic
                    response = await http_client.fetch(server)  
                    # If we receive a response, mark the server as alive
                    self.server_pool[server] = True
                    logger.info(f"{server} is alive")
                except tornado.httpclient.HTTPClientError as e:
                    # If the request fails, mark the server as down
                    self.server_pool[server] = False
                    logger.warning(f"{server} is down: {e}")
                except Exception as e:
                    # TODO: handle this
                    self.server_pool[server] = False
                    logger.warning(f"{server} is down: {e}")

    def start(self):
        if self.enabled:
            tornado.ioloop.PeriodicCallback(self.perform_check, self.interval).start()

class Strategy:
    def route(self, request, server_pool):
        raise NotImplementedError("Subclasses should implement this method.")

class RoundRobin(Strategy):
    def __init__(self):
        self.index = 0

    def route(self, request, server_pool):
        # Convert the keys of the server_pool dict into a list
        active_servers = [server for server, is_alive in server_pool.items() if is_alive]
        
        # Check if there are any active servers
        if not active_servers:
            raise Exception("No available servers")

        # Use the round-robin approach to select the server
        server = active_servers[self.index % len(active_servers)]
        self.index += 1
        
        return server

class LeastConnections(Strategy):
    def route(self, request, server_pool):
        # Implement logic to find the server with the least connections
        # This is just a placeholder
        return min(server_pool, key=lambda s: s.connections)


class Router:
    def __init__(self, config, server_pool):
        self.server_pool = server_pool
        routing_config = config.get('routing', {})
        # if strategy key is emtpy, round_robin is assigned to strategy_name
        strategy_name = routing_config.get('strategy', 'round_robin')
        print("Selected strategy", strategy_name)

        # Select the appropriate strategy based on the config
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
        print(f"Routing request to {server} using {self.strategy.__class__.__name__} strategy")
        return server
