# config_manager.py - Gestione configurazione YAML
import yaml
import os
from pathlib import Path

class ConfigManager:
    def __init__(self, config_file='config/config.yaml'):
        self.config = None
        self.config_file = Path(config_file)
        self.load_config()

    def load_config(self):
        try:
            with open(self.config_file, 'r') as f:
                self.config = yaml.safe_load(f)
        except FileNotFoundError:
            raise Exception(f"File di configurazione non trovato: {self.config_file}")
        except yaml.YAMLError as e:
            raise Exception(f"Errore nel parsing del file YAML: {str(e)}")


    def get_rabbitmq_config(self):
        return self.config.get('rabbitmq', {})

    def get_infrastructure_config(self):
        return self.config.get('infrastructure', {})