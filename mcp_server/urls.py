"""
URL configuration for mcpexample project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to ur lpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.contrib import admin
from django.urls import path, include
from django.utils.module_loading import import_string
from rest_framework.permissions import IsAuthenticated

from mcp_server.views import MCPServerStreamableHttpView, MCPServerStreamableHttpOnlyView
from mcp_server.content_negotiation import MCPContentNegotiation
from django.http import JsonResponse


def health_check(request):
    """Simple health check endpoint"""
    return JsonResponse({"status": "ok"})


# Register MCP Server View and bypass default DRF default permission / authentication classes
urlpatterns = [
    # Health check endpoint
    path("health/", health_check, name="health_check"),
    # Original MCP endpoint for JSON-RPC calls
    path("mcp", MCPServerStreamableHttpView.as_view(
        permission_classes=[IsAuthenticated] if getattr(settings, 'DJANGO_MCP_AUTHENTICATION_CLASSES', None) else [],
        authentication_classes=[import_string(cls) for cls in getattr(settings, 'DJANGO_MCP_AUTHENTICATION_CLASSES', [])],
        content_negotiation_class=MCPContentNegotiation
    ), name="mcp_server_streamable_http_endpoint"),
    
    # Streamable HTTP-only endpoint
    path("mcp/http", MCPServerStreamableHttpOnlyView.as_view(
        permission_classes=[IsAuthenticated] if getattr(settings, 'DJANGO_MCP_AUTHENTICATION_CLASSES', None) else [],
        authentication_classes=[import_string(cls) for cls in getattr(settings, 'DJANGO_MCP_AUTHENTICATION_CLASSES', [])],
        content_negotiation_class=MCPContentNegotiation
    ), name="mcp_server_http_only_endpoint"),
 
    # SSE endpoint for Server-Sent Events
    path("mcp/sse", MCPServerStreamableHttpView.as_view(
        permission_classes=[IsAuthenticated] if getattr(settings, 'DJANGO_MCP_AUTHENTICATION_CLASSES', None) else [],
        authentication_classes=[import_string(cls) for cls in getattr(settings, 'DJANGO_MCP_AUTHENTICATION_CLASSES', [])],
        content_negotiation_class=MCPContentNegotiation
    ), name="mcp_server_sse_endpoint"),
    
    # Messages endpoint for SSE message posting
    path("mcp/messages/", MCPServerStreamableHttpView.as_view(
        permission_classes=[IsAuthenticated] if getattr(settings, 'DJANGO_MCP_AUTHENTICATION_CLASSES', None) else [],
        authentication_classes=[import_string(cls) for cls in getattr(settings, 'DJANGO_MCP_AUTHENTICATION_CLASSES', [])],
        content_negotiation_class=MCPContentNegotiation
    ), name="mcp_server_messages_endpoint"),
] 