import yaml

class Config:
    def __init__(self, config_file):
        self.config_data = self.load_config(config_file)

    def load_config(self, config_file):
        with open(config_file, 'r') as file:
            return yaml.safe_load(file)

    def get(self, key, default=None):
        return self.config_data.get(key, default)

