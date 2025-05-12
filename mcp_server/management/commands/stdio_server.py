from django.core.management.base import BaseCommand
from mcp_server import mcp_server


class Command(BaseCommand):
    help = 'Run the global mcp server over STDIO transport'

    def handle(self, *args, **options):
        mcp_server.run(transport="stdio")