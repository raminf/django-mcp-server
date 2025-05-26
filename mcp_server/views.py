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

    def dispatch(self, request, *args, **kwargs):
        """Override dispatch to handle SSE requests before DRF content negotiation"""
        # Check if this is an SSE request by path or Accept header
        if (request.path.endswith('/sse') or 
            'text/event-stream' in request.headers.get('Accept', '')):
            # Handle SSE connection directly, bypassing DRF content negotiation
            return self._handle_sse_connection(request)
        
        # For non-SSE requests, use normal DRF handling
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        # Handle regular GET request (JSON-RPC)
        return self.mcp_server.handle_django_request(request)

    def post(self, request, *args, **kwargs):
        return self.mcp_server.handle_django_request(request)

    def delete(self, request, *args, **kwargs):
        self.mcp_server.destroy_session(request)
        return HttpResponse(status=200, content="Session destroyed")

    def _handle_sse_connection(self, request):
        """Handle Server-Sent Events connection for MCP"""
        import uuid
        import time
        from datetime import datetime
        
        # Generate session ID if not present
        session_id = getattr(request.session, 'session_key', None) if hasattr(request, 'session') else None
        if not session_id:
            session_id = str(uuid.uuid4())
        
        def event_stream():
            # Send initial SSE headers
            yield "event: endpoint\n"
            yield f"data: /mcp/messages/?session_id={session_id}\n\n"
            
            # Keep connection alive with periodic pings
            while True:
                yield f": ping - {datetime.now().strftime('%Y-%m-%d %H:%M:%S%z')}\n\n"
                time.sleep(30)  # Send ping every 30 seconds

        response = StreamingHttpResponse(
            event_stream(),
            content_type='text/event-stream'
        )
        response['Cache-Control'] = 'no-cache'
        # CRITICAL: Do NOT set Connection: keep-alive - causes WSGI errors
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Headers'] = 'Cache-Control'
        return response 

# Streamable HTTP support
@method_decorator(csrf_exempt, name='dispatch')
class MCPServerStreamableHttpOnlyView(APIView):
    """MCP Server view that supports only streamable HTTP (no SSE)"""
    mcp_server = global_mcp_server

    def get(self, request, *args, **kwargs):
        # Handle streamable HTTP GET requests
        return self._handle_streamable_http(request)

    def post(self, request, *args, **kwargs):
        # Handle streamable HTTP POST requests
        return self._handle_streamable_http(request)

    def delete(self, request, *args, **kwargs):
        self.mcp_server.destroy_session(request)
        return HttpResponse(status=200, content="Session destroyed")

    def _handle_streamable_http(self, request):
        """Handle streamable HTTP requests without SSE"""
        # Check if client expects streaming response
        if 'application/json-stream' in request.headers.get('Accept', ''):
            return self._create_streaming_response(request)
        else:
            # Handle regular JSON-RPC request
            return self.mcp_server.handle_django_request(request)

    def _create_streaming_response(self, request):
        """Create a streaming HTTP response"""
        import uuid
        import json
        from datetime import datetime
        
        session_id = getattr(request.session, 'session_key', None) if hasattr(request, 'session') else None
        if not session_id:
            session_id = str(uuid.uuid4())
        
        def json_stream():
            # Send initial connection info as JSON
            initial_data = {
                "type": "connection",
                "session_id": session_id,
                "endpoint": f"/mcp/messages/?session_id={session_id}",
                "timestamp": datetime.now().isoformat()
            }
            yield json.dumps(initial_data) + '\n'
            
            # Keep connection alive with periodic heartbeats
            import time
            while True:
                heartbeat = {
                    "type": "heartbeat",
                    "timestamp": datetime.now().isoformat()
                }
                yield json.dumps(heartbeat) + '\n'
                time.sleep(30)  # Send heartbeat every 30 seconds

        response = StreamingHttpResponse(
            json_stream(),
            content_type='application/json-stream'  # Custom content type for JSON streaming
        )
        response['Cache-Control'] = 'no-cache'
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Headers'] = 'Accept, Content-Type, Authorization'
        return response
