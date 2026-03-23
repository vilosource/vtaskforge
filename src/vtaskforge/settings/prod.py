"""
Production settings for vtaskforge.
"""
import os

from .base import *  # noqa: F401,F403

DEBUG = False

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '').split(',')

# CORS — allow origins matching ALLOWED_HOSTS
CORS_ALLOWED_ORIGINS = [
    f"https://{host}" for host in ALLOWED_HOSTS if host and not host.startswith('.')
]

# CSRF — trust the same origins
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS.copy()

# Secure cookies over HTTPS
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
