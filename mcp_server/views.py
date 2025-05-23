# In mcp_server/views.py

from django.conf import settings
from django.http import HttpResponse, StreamingHttpResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from mcp.server import FastMCP
from rest_framework.views import APIView

from mcp_server.djangomcp import global_mcp_server


@method_decorator(csrf_exempt, name='dispatch')
class MCPServerStreamableHttpView(APIView):
    mcp_server = global_mcp_server

    def get(self, request, *args, **kwargs):
        # Check if this is an SSE connection request
        accept_header = request.headers.get('Accept', '')
        if 'text/event-stream' in accept_header:
            # Handle SSE connection
            return self._handle_sse_connection(request)
        else:
            # Handle regular GET request (JSON-RPC)
            return self.mcp_server.handle_django_request(request)

    def post(self, request, *args, **kwargs):
        return self.mcp_server.handle_django_request(request)

    def delete(self, request, *args, **kwargs):
        self.mcp_server.destroy_session(request)
        return HttpResponse(status=200, content="Session destroyed")

    def _handle_sse_connection(self, request):
        """Handle Server-Sent Events connection for MCP"""
        def event_stream():
            # Send initial SSE headers
            yield "event: endpoint\n"
            yield f"data: /mcp/messages/?session_id={request.session.session_key if hasattr(request, 'session') else 'default'}\n\n"
            
            # Keep connection alive with periodic pings
            import time
            while True:
                yield f": ping - {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                time.sleep(30)  # Send ping every 30 seconds

        response = StreamingHttpResponse(
            event_stream(),
            content_type='text/event-stream'
        )
        response['Cache-Control'] = 'no-cache'
        response['Connection'] = 'keep-alive'
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Headers'] = 'Cache-Control'
        return response
        
