"""Render/WSGI entrypoint for Isazi Client Portal."""
from app import create_app

app = create_app()
