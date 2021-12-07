import os


def get(var: str):
    return os.getenv(f"PYT_{var.upper()}")
