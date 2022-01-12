import os

from flask.cli import load_dotenv

load_dotenv()


def get(var: str, default=None):
    return os.getenv(f"PYT_{var.upper()}", default)
