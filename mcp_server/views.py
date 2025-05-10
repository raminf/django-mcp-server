from django.conf import settings
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from mcp.server import FastMCP

from mcp_server.djangomcp import global_mcp_server


@method_decorator(csrf_exempt, name='dispatch')
class MCPServerStreamableHttpView(View):
    mcp_server = global_mcp_server

    def dispatch(self, request, *args, **kwargs):
        return self.mcp_server.handle_django_request(request)

