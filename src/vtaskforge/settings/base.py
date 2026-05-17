"""
Base Django settings for vtaskforge.
Shared across all environments.
"""
import os
from datetime import timedelta

import dj_database_url

# SECURITY
SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-insecure-key-change-in-prod')

DEBUG = False

ALLOWED_HOSTS = []

# Application definition
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    'django_celery_beat',
    'drf_spectacular',
]

LOCAL_APPS = [
    'core',
    'projects',
    'workplans',
    'tasks',
    'links',
    'reviews',
    'events',
    'agents',
    'prefs',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'core.idempotency.IdempotencyMiddleware',
    'core.location_header.LocationHeaderMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'vtaskforge.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'vtaskforge.wsgi.application'

# Database
DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get('DATABASE_URL'),
    )
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = 'static/'
STATIC_ROOT = os.environ.get('STATIC_ROOT', '/app/staticfiles')

# SPA build output is copied to /app/static/spa in production (Dockerfile.prod)
STATICFILES_DIRS = []

# WhiteNoise: serve static files with compression and cache headers
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'core.pagination.VTFCursorPagination',
    'PAGE_SIZE': 50,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'EXCEPTION_HANDLER': 'core.exception_handler.v2_exception_handler',
    'DEFAULT_VERSIONING_CLASS': 'core.versioning.URLPrefixVersioning',
    'ALLOWED_VERSIONS': ['v1', 'v2'],
    'DEFAULT_VERSION': 'v1',
}

# OpenAPI / drf-spectacular
SPECTACULAR_SETTINGS = {
    'TITLE': 'vtaskforge v2 API',
    'DESCRIPTION': 'Distributed task execution system for LLM agents',
    'VERSION': '2.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'SCHEMA_PATH_PREFIX': r'/v2/',
}

# Agent fleet
AGENT_STALE_THRESHOLD_SECONDS = 300  # 5 minutes without heartbeat = stale

# Celery
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'

CELERY_BEAT_SCHEDULE = {
    'expire-stale-claims': {
        'task': 'tasks.celery_tasks.expire_stale_claims',
        'schedule': timedelta(seconds=60),
    },
    # R3 (I2 backstop for vafi#18): escalate stalled
    # pending_completion_review tasks. Sibling of the claim reaper.
    'expire-stale-reviews': {
        'task': 'tasks.celery_tasks.expire_stale_reviews',
        'schedule': timedelta(seconds=60),
    },
}

# R3: review-phase lease duration (minutes). Aligns with the claim
# timeout default. Single source consumed by tasks.state_machine.
REVIEW_TIMEOUT_MINUTES = int(os.environ.get('VTF_REVIEW_TIMEOUT_MINUTES', '30'))

# CXDB — execution trace store (read-only consumer)
CXDB_BASE_URL = os.environ.get('CXDB_BASE_URL', 'http://cxdb-server.vafi-agents.svc.cluster.local')
CXDB_WEB_URL = os.environ.get('CXDB_WEB_URL', CXDB_BASE_URL)
CXDB_TIMEOUT_CONNECT = float(os.environ.get('CXDB_TIMEOUT_CONNECT', '3.0'))
CXDB_TIMEOUT_READ = float(os.environ.get('CXDB_TIMEOUT_READ', '5.0'))
