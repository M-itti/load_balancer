import tornado.ioloop
import tornado.web
import tornado.httpserver
import multiprocessing
from multiprocessing import Manager
import threading
import yaml
import os

from balancer import Router, HealthCheck, ReverseProxy
from logging_config import logger
from config_parser import Config

# TODO: add graceful shutdown (pkill python, pkill Python)

class LoadBalancer:
    def __init__(self, config_file):
        self.config = Config(config_file)
        self.listen_port = self.config.get('listen_port', 8080)
        self.default_workers = os.cpu_count()  
        
        manager = Manager()
        self.server_pool = manager.dict({
            server_url: manager.dict({"connections": 0, "alive": True})
            for server_url in self.config.get('server_pool')
        })

        self.router = Router(self.config, self.server_pool)
        self.health_check = HealthCheck(self.config, self.server_pool)

        logger.info(f'Starting proxy server on port {self.listen_port}...')
        self.app = tornado.web.Application([
            (r"/.*", ReverseProxy,
             dict(server_pool=self.server_pool, router=self.router)),
        ])

        self.http_server = tornado.httpserver.HTTPServer(self.app)

        self.http_server.bind(self.listen_port)

    def start_health_check(self):
        """Start health checks in a separate thread."""
        health_check_thread = threading.Thread(
            target=self.health_check.start
        )
        health_check_thread.start()
        logger.info("Health check started.")

    def start_reverse_proxy(self):
        num_workers = self.config.get('worker_processes', self.default_workers)  
        self.http_server.start(num_workers)  
        tornado.ioloop.IOLoop.current().start()

    def main(self):
        self.start_health_check()
        self.start_reverse_proxy()

if __name__ == "__main__":
    lb = LoadBalancer('config.yaml')
    lb.main() 
