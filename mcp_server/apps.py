from django.apps import AppConfig
from django.utils.module_loading import autodiscover_modules


class McpServerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "mcp_server"

    def ready(self):
        autodiscover_modules('mcp')
