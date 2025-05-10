from functools import cached_property

import anyio
from django.conf import settings
from mcp.server import FastMCP
from mcp.server.sse import SseServerTransport
from mcp.server.streamable_http import StreamableHTTPServerTransport
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

from django.http import HttpResponse
from asgiref.compatibility import guarantee_single_callable
from asgiref.wsgi import WsgiToAsgi
from starlette.types import Scope, Receive, Send
from starlette.datastructures import Headers
from io import BytesIO
import asyncio

# --- assuming your transport is imported as StreamableHTTPServerTransport
# from yourmodule import StreamableHTTPServerTransport

async def call_starlette_handler(django_request, session_manager):
    """
    Adapts a Django request into a Starlette request and calls transport.handle_request.

    Returns:
        A Django HttpResponse
    """

    # Build ASGI scope
    scope: Scope = {
        "type": "http",
        "http_version": "1.1",
        "method": django_request.method,
        "headers": [
            (key.lower().encode("latin-1"), value.encode("latin-1"))
            for key, value in django_request.headers.items()
        ],
        "path": django_request.path,
        "raw_path": django_request.get_full_path().encode("utf-8"),
        "query_string": django_request.META["QUERY_STRING"].encode("latin-1"),
        "scheme": "https" if django_request.is_secure() else "http",
        "client": (django_request.META.get("REMOTE_ADDR"), 0),
        "server": (django_request.get_host(), django_request.get_port()),
    }

    # Provide receive function to return body (once)
    body = django_request.body

    async def receive() -> Receive:
        return {
            "type": "http.request",
            "body": body,
            "more_body": False,
        }

    # Prepare to collect send events
    response_started = {}
    response_body = bytearray()

    async def send(message: Send):
        if message["type"] == "http.response.start":
            response_started["status"] = message["status"]
            response_started["headers"] = Headers(raw=message["headers"])
        elif message["type"] == "http.response.body":
            response_body.extend(message.get("body", b""))

    async with session_manager.run():
    # Call transport
        await session_manager.handle_request(scope, receive, send)

    # Build Django HttpResponse
    status = response_started.get("status", 500)
    headers = response_started.get("headers", {})

    response = HttpResponse(
        bytes(response_body),
        status=status,
    )
    for key, value in headers.items():
        response[key] = value #.decode("latin-1")

    return response



# FIXME: shall I reimplement the necessary without the
# Stuff pulled to support embedded server ?
class DjangoMCP(FastMCP):

    @property
    def session_manager(self) -> StreamableHTTPSessionManager:
        return StreamableHTTPSessionManager(
            app=self._mcp_server,
            event_store=self._event_store,
            json_response=True,
            stateless=True,  # TODO: enable sessions ? Use the stateless setting
        )

    def handle_django_request(self, request):
        """
        Handle a Django request and return a response.
        This method is called by the Django view when a request is received.
        """

        return anyio.run(call_starlette_handler,request, self.session_manager)


global_mcp_server = DjangoMCP(**settings.DJANGO_MCP_GLOBAL_SERVER_CONFIG) if getattr(settings, 'DJANGO_MCP_GLOBAL_SERVER_CONFIG', None) else None



"""
    use : https://modelcontextprotocol.io/docs/concepts/transports#python-server
    wuth custom transport

    the server is self._mcp_server
global_mcp_server = DjangoMCP(settings.DMCP_GLOBAL_SERVER_NAME) if getattr(settings, 'DMCP_GLOBAL_SERVER_NAME', None) else None



mcp_server.streamable_http_app()
Then mcp_server.session_manager


use StreamableHTTPSessionManager ?

or directly http_transport = StreamableHTTPServerTransport(
            mcp_session_id=None,  # No session tracking in stateless mode
            is_json_response_enabled=self.json_response,
            event_store=None,  # No event store in stateless mode
        )

        # Start server in a new task
        async def run_stateless_server(
            *, task_status: TaskStatus[None] = anyio.TASK_STATUS_IGNORED
        ):
            async with http_transport.connect() as streams:
                read_stream, write_stream = streams
                task_status.started()
                await self.app.run(
                    read_stream,
                    write_stream,
                    self.app.create_initialization_options(),
                    stateless=True,


"""