import logging
import tornado.ioloop
import tornado.web
from balancer import *

class LoadBalancer:
    def __init__(self, config_file):
        
        # TODO: pool is hard-coded
        self.server_pool = {server: True for server in [
            "http://localhost:2000",
            "http://localhost:3000",
            "http://localhost:4000"
            ]}

        self.config = Config(config_file)
        self.workers = []
        self.router = Router(self.config, self.server_pool)
        self.health_check = HealthCheck(self.config, self.server_pool)
        self.setup_workers()
        
        print(f'Starting proxy server on port 8080...')
        self.app = tornado.web.Application([
            (r"/.*", ReverseProxy,
             dict(server_pool=self.server_pool, router=self.router)),  
        ])
        self.app.listen(8080)

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
    
