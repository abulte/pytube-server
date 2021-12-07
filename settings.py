import os


def get(var: str, default=None):
    return os.getenv(f"PYT_{var.upper()}", default)
