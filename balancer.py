import itertools
import threading
import time
import requests
from requests.exceptions import RequestException
from requests.adapters import HTTPAdapter, Retry
from http.server import BaseHTTPRequestHandler, HTTPServer
import logging
import yaml

import logging_config

logger = logging.getLogger(__name__)

class Config:
    def __init__(self, config_file):
        self.config_data = self.load_config(config_file)

    def load_config(self, config_file):
        with open(config_file, 'r') as file:
            return yaml.safe_load(file)

    def get(self, key, default=None):
        return self.config_data.get(key, default)

class ReverseProxy(BaseHTTPRequestHandler):
    def do_GET(self):
        #url = self.server_manager.get_next_server()
        url = "http://localhost:2000"
        response = self.attempt_request(url)

        if response:
            self.send_response(response.status_code)
            self.send_header('Content-type', response.headers.get('Content-Type', 'text/plain'))
            self.end_headers()
            self.wfile.write(response.content)
        else:
            self.send_error(502, 'Bad Gateway')

    def attempt_request(self, url):
        logger.info(f"Forwarding request to: {url}")

        with self.create_session() as session:
            try:
                response = session.get(url + self.path, headers=dict(self.headers))
                response.raise_for_status()
                return response
            except requests.RequestException as e:
                logger.error(f"Request failed: {e}")
                return None

    def create_session(self):
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session

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

class HealthCheck:
    def __init__(self, config):
        self.enabled = config.get('health_check', {}).get('enabled', False)
        self.interval = config.get('health_check', {}).get('interval', 10)

    def perform_check(self):
        if self.enabled:
            print("Performing health check")
            # Implement health-check logic

class Router:
    def __init__(self, config):
        self.strategy = config.get('routing', {}).get('strategy', 'round_robin')

    def route_request(self, request):
        print(f"Routing request using {self.strategy} strategy")
        # Implement routing logic
