"""Модуль приложения API для проекта Foodgram.

Содержит конфигурацию Django-приложения 'api', включающую:
- регистрацию приложения в проекте,
- настройку поля по умолчанию для автоинкрементных ID.
"""

from django.apps import AppConfig


class ApiConfig(AppConfig):
    """Конфигурация приложения API."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'
