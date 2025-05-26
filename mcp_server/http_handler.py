import json
import time
from django.http import StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt


class HTTPStreamHandler:
    def __init__(self, mcp_server):
        self.mcp_server = mcp_server
        self.connections = {}

    def handle_http_stream_connection(self, request):
        """Handle HTTP streaming connection establishment"""
        session_id = self._get_or_create_session_id(request)
        
        def json_stream():
            try:
                # Send initial connection event as JSON
                initial_data = {
                    "type": "connection",
                    "session_id": session_id,
                    "endpoint": f"/mcp/messages/?session_id={session_id}",
                    "timestamp": time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3] + '+00:00'
                }
                yield json.dumps(initial_data) + '\n'
                
                # Store connection
                self.connections[session_id] = True
                
                # Keep connection alive with JSON heartbeats
                while self.connections.get(session_id, False):
                    heartbeat = {
                        "type": "heartbeat",
                        "timestamp": time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3] + '+00:00'
                    }
                    yield json.dumps(heartbeat) + '\n'
                    time.sleep(30)
                    
            except GeneratorExit:
                # Clean up when connection closes
                self.connections.pop(session_id, None)
            except Exception as e:
                print(f"HTTP Stream Error: {e}")
                self.connections.pop(session_id, None)

        response = StreamingHttpResponse(
            json_stream(),
            content_type='application/json-stream'
        )
        response['Cache-Control'] = 'no-cache'
        response['Connection'] = 'keep-alive'
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Headers'] = 'Accept, Content-Type, Authorization'
        
        return response

    def _get_or_create_session_id(self, request):
        """Get or create a session ID for the connection"""
        if hasattr(request, 'session') and request.session.session_key:
            return request.session.session_key
        else:
            import uuid
            return str(uuid.uuid4())

    def close_connection(self, session_id):
        """Close a specific HTTP stream connection"""
        self.connections.pop(session_id, None)
  
