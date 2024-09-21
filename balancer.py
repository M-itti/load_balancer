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

# Reverse Proxy Handler (replaces BaseHTTPRequestHandler)
class ReverseProxy(tornado.web.RequestHandler):
    async def get(self):
        #url = self.application.server_manager.get_next_server() # You can implement this
        url = "http://localhost:2000"
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
    def __init__(self, config):
        self.enabled = config.get('health_check', {}).get('enabled', False)
        self.interval = config.get('health_check', {}).get('interval', 10)

    def perform_check(self):
        if self.enabled:
            print("Performing health check")
            # Implement health-check logic

# Router Class
class Router:
    def __init__(self, config):
        self.strategy = config.get('routing', {}).get('strategy', 'round_robin')

    def route_request(self, request):
        print(f"Routing request using {self.strategy} strategy")
        # Implement routing logic

# Main application setup
def make_app():
    return tornado.web.Application([
        (r"/.*", ReverseProxy),  # Proxying all paths
    ])

if __name__ == "__main__":
    config = Config('config.yaml')  # Load your YAML config file
    app = make_app()
    app.listen(8080)
    print("Server running on http://0.0.0.0:8080")
    tornado.ioloop.IOLoop.current().start()
