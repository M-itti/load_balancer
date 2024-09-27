import tornado.ioloop
import tornado.web
import tornado.httpserver
import multiprocessing
import yaml
import os

from balancer import Router, HealthCheck, ReverseProxy
from logging_config import logger
from config_parser import Config

# TODO: add graceful shutdown

# TODO: active servers are local to the route!! must be global

class LoadBalancer:
    def __init__(self, config_file):
        self.config = Config(config_file)
        self.listen_port = self.config.get('listen_port', 8080)
        
        self.server_pool = {
            server_url: {"connections": 0, "alive": True} 
            for server_url in self.config.get('server_pool')
        }

        self.router = Router(self.config, self.server_pool)
        logger.info(f'Starting proxy server on port {self.listen_port}...')
        self.app = tornado.web.Application([
            (r"/.*", ReverseProxy,
             dict(server_pool=self.server_pool, router=self.router)),
        ])

        # Create the HTTP server instance
        self.http_server = tornado.httpserver.HTTPServer(self.app)

        # Bind the server to the specified port
        self.http_server.bind(self.listen_port)

    def start_health_check(self):
        """Start health checks in a separate process."""
        health_check_process = multiprocessing.Process(
            target=self.health_check.perform_check
        )
        health_check_process.start()
        logger.info("Health check started.")

    def start_reverse_proxy(self):
        # TODO: this function is being called n workers times 
        default_workers = os.cpu_count()  
        num_workers = self.config.get('worker_processes', default_workers)  
        self.http_server.start(num_workers)  
        tornado.ioloop.IOLoop.current().start()

    def main(self):
        #self.start_health_check()
        self.start_reverse_proxy()

if __name__ == "__main__":
    lb = LoadBalancer('config.yaml')
    lb.main()
