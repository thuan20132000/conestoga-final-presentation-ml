from django.apps import AppConfig


class ServiceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "service"
    verbose_name = "Service Management"

    def ready(self):
        import service.signals  # noqa: F401
