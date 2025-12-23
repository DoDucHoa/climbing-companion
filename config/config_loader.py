import yaml
from typing import Dict
import os


class ConfigLoader:
    @staticmethod
    def load_database_config(config_path: str = "config/database.yaml") -> Dict:
        """Load database configuration from YAML file"""
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        if not config or "database" not in config:
            raise ValueError("Invalid configuration file: missing database section")

        return config["database"]

    @staticmethod
    def build_connection_string(config: Dict) -> str:
        """Build MongoDB connection string from configuration
        
        Supports two modes:
        1. Cloud/Atlas: Use 'connection_string' directly from config
        2. Local: Build from 'connection' parameters (host, port, username, password)
        """
        # Priority 1: Use direct connection string if provided (for cloud databases)
        if config.get("connection_string") and config["connection_string"].strip():
            return config["connection_string"].strip()
        
        # Priority 2: Build from connection parameters (for local MongoDB)
        conn = config["connection"]
        host = conn["host"]
        port = conn["port"]

        # Build authentication part if credentials are provided
        auth = ""
        if conn.get("username") and conn.get("password"):
            auth = f"{conn['username']}:{conn['password']}@"

        return f"mongodb://{auth}{host}:{port}"