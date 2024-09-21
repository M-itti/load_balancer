from balancer import *
import logging

class LoadBalancer:
    def __init__(self, config_file):
        self.config = Config(config_file)
        self.workers = []
        self.router = Router(self.config)
        self.health_check = HealthCheck(self.config)
        self.setup_workers()
        
        print(f'Starting proxy server on port 8080...')
        server = HTTPServer(('0.0.0.0', 8080), ReverseProxy)
        server.serve_forever()

    def setup_workers(self):
        worker_count = self.config.get('worker_processes', 4)
        for i in range(worker_count):
            worker = Worker(i)
            self.workers.append(worker)

    def start(self):
        for worker in self.workers:
            worker.start()
        if self.health_check.enabled:
            self.health_check.perform_check()

    def route_request(self, request):
        self.router.route_request(request)


if __name__ == "__main__":
    lb = LoadBalancer('config.yaml')
    lb.start()
    
    # Simulate a request
    lb.route_request('Request 1')
