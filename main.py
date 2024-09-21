import logging
import tornado.ioloop
import tornado.web
from balancer import *

class LoadBalancer:
    def __init__(self, config_file):
        self.config = Config(config_file)
        self.workers = []
        self.router = Router(self.config)
        self.health_check = HealthCheck(self.config)
        self.setup_workers()
        
        print(f'Starting proxy server on port 8080...')
        self.app = tornado.web.Application([
            (r"/.*", ReverseProxy),  # Route all requests to ReverseProxy
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

    def route_request(self, request):
        self.router.route_request(request)

if __name__ == "__main__":
    lb = LoadBalancer('config.yaml')
    lb.start()
    
    # Simulate a request (you could remove this if not needed)
    lb.route_request('Request 1')
