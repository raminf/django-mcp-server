import asyncio
import json
import time
from django.http import StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator


class SSEHandler:
    def __init__(self, mcp_server):
        self.mcp_server = mcp_server
        self.connections = {}

    def handle_sse_connection(self, request):
        """Handle SSE connection establishment"""
        session_id = self._get_or_create_session_id(request)
        
        def event_stream():
            try:
                # Send initial connection event
                yield f"event: endpoint\n"
                yield f"data: /mcp/messages/?session_id={session_id}\n\n"
                
                # Store connection
                self.connections[session_id] = True
                
                # Keep connection alive
                while self.connections.get(session_id, False):
                    yield f": ping - {time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}+00:00\n\n"
                    time.sleep(30)
                    
            except GeneratorExit:
                # Clean up when connection closes
                self.connections.pop(session_id, None)
            except Exception as e:
                print(f"SSE Error: {e}")
                self.connections.pop(session_id, None)

        response = StreamingHttpResponse(
            event_stream(),
            content_type='text/event-stream'
        )
        response['Cache-Control'] = 'no-cache'
        response['Connection'] = 'keep-alive'
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Headers'] = 'Cache-Control'
        response['X-Accel-Buffering'] = 'no'  # Disable nginx buffering
        
        return response

    def _get_or_create_session_id(self, request):
        """Get or create a session ID for the connection"""
        if hasattr(request, 'session') and request.session.session_key:
            return request.session.session_key
        else:
            import uuid
            return str(uuid.uuid4())

    def close_connection(self, session_id):
        """Close a specific SSE connection"""
        self.connections.pop(session_id, None)
      
