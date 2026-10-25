"""Entry point for hosting (gunicorn). Starts the database, ML models and sensor simulator once."""
from app import app, boot

boot()
