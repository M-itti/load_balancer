import logging
from config_parser import Config

config = Config("config.yaml")

log_level_str = config.get('logging', {}).get('level', 'INFO').upper()

log_levels = {
    'CRITICAL': logging.CRITICAL,
    'ERROR': logging.ERROR,
    'WARNING': logging.WARNING,
    'INFO': logging.INFO,
    'DEBUG': logging.DEBUG,
    'NOTSET': logging.NOTSET,
}

log_level = log_levels.get(log_level_str, logging.INFO)

log_file = config.get('logging', {}).get('file', '')

handlers = [logging.StreamHandler()]  

if log_file:
    handlers.append(logging.FileHandler(log_file))  

logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=handlers,
)

logger = logging.getLogger('balancer')
