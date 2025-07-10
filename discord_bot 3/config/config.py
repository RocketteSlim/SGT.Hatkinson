import json
import os

class BotConfig:
    def __init__(self, config_path="config.json"):
        self.config_path = config_path
        self.command_states = {}
        self.command_roles = {}
        self.embed_channel_id = None
        self.load_config()

    def load_config(self):
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                    self.command_states = config.get('command_states', {})
                    self.command_roles = config.get('command_roles', {})
                    self.embed_channel_id = config.get('embed_channel_id')
                    print("Configuration chargée avec succès")
            else:
                print(f"Fichier {self.config_path} introuvable, création d'une configuration par défaut")
                self.save_config()
        except Exception as e:
            print(f"Erreur lors du chargement de la configuration : {e}")

    def save_config(self):
        try:
            with open(self.config_path, 'w') as f:
                json.dump({
                    'command_states': self.command_states,
                    'command_roles': self.command_roles,
                    'embed_channel_id': self.embed_channel_id
                }, f, indent=4)
            print("Configuration sauvegardée avec succès")
        except Exception as e:
            print(f"Erreur lors de la sauvegarde de la configuration : {e}")

    def is_command_enabled(self, command_name):
        return self.command_states.get(command_name, False)

    def set_command_state(self, command_name, state):
        self.command_states[command_name] = state
        self.save_config()

    def get_authorized_roles(self, command_name):
        return self.command_roles.get(command_name, [])

    def set_authorized_roles(self, command_name, role_ids):
        self.command_roles[command_name] = role_ids
        self.save_config()