import tornado.ioloop
import tornado.web

from balancer import Config, Router, HealthCheck, Worker, ReverseProxy
from logging_config import logger
from config_parser import Config

class LoadBalancer:
    def __init__(self, config_file):
        self.config = Config(config_file)
        self.listen_port = self.config.get('listen_port', 8080)  
        self.server_pool = {
            server_url: {"connections": 0, "alive": True} 
            for server_url in self.config.get('server_pool')
        }
        self.workers = []
        self.router = Router(self.config, self.server_pool)
        self.health_check = HealthCheck(self.config, self.server_pool)
        self.setup_workers()
        
        logger.info(f'Starting proxy server on port {self.listen_port}...')
        self.app = tornado.web.Application([
            (r"/.*", ReverseProxy,
             dict(server_pool=self.server_pool, router=self.router)),  
        ])

        self.app.listen(self.listen_port)

    def setup_workers(self):
        worker_count = self.config.get('worker_processes', 4)
        for i in range(worker_count):
            worker = Worker(i)
            self.workers.append(worker)

    def start(self):
        for worker in self.workers:
            worker.start()
        if self.health_check.enabled:
            tornado.ioloop.PeriodicCallback(self.health_check.perform_check, self.health_check.interval * 1000).start()
        
        tornado.ioloop.IOLoop.current().start()

if __name__ == "__main__":
    lb = LoadBalancer('config.yaml')
    lb.start()
    
