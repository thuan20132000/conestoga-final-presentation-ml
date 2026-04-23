"""
ASGI config for main project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')

application = get_asgi_application()
"""
ASGI config for main project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application
from starlette.applications import Starlette
from starlette.routing import Mount

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')

# Django ASGI app
django_app = get_asgi_application()

# Import FastAPI app
from ai_service.main import app as fastapi_app

# Composite ASGI app:
# - FastAPI served at /ai-service
# - Django served at /
application = Starlette(
    routes=[
        Mount("/ai-service", app=fastapi_app),
        Mount("/", app=django_app),
    ]
)