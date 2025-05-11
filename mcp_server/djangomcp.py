import inspect
from functools import cached_property

import anyio
from asgiref.sync import sync_to_async
from django.conf import settings
from mcp.server import FastMCP
from mcp.server.sse import SseServerTransport
from mcp.server.streamable_http import StreamableHTTPServerTransport
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

from django.http import HttpResponse
from asgiref.compatibility import guarantee_single_callable
from asgiref.wsgi import WsgiToAsgi
from mcp.types import AnyFunction, ToolAnnotations
from pyarrow._fs import ABC
from starlette.types import Scope, Receive, Send
from starlette.datastructures import Headers
from io import BytesIO
import asyncio


async def call_starlette_handler(django_request, session_manager):
    """
    Adapts a Django request into a Starlette request and calls session_manager.handle_request.

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
        response[key] = value

    return response


class _ToolsetMethodCaller:

    def __init__(self, class_, method_name, context_kwarg, forward_context_kwarg):
        self.class_ = class_
        self.method_name = method_name
        self.context_kwarg = context_kwarg
        self.forward_context_kwarg = forward_context_kwarg

    def __call__(self, *args, **kwargs):
        # Get the class instance
        instance = self.class_(context=kwargs[self.context_kwarg])

        # Get the method
        method = sync_to_async(getattr(instance, self.method_name))
        if not self.forward_context_kwarg:
            # Remove the context kwarg from kwargs
            del kwargs[self.context_kwarg]

        return method(*args, **kwargs)


# FIXME: shall I reimplement the necessary without the
# Stuff pulled to support embedded server ?
class DjangoMCP(FastMCP):

    def __init__(self, name=None, instructions=None):
        # Prevent extra server settings as we do not use the embedded server
        super().__init__(name or "django_mcp_server", instructions)

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

    def register_mcptoolset_cls(self, cls):
        instance = cls()
        # ITerate all the methods whose name does not start with _ and register them with mcp_server.add_tool
        for name, method in inspect.getmembers(instance, predicate=inspect.ismethod):
            if not callable(method) or name.startswith("_"): continue
            tool = self._tool_manager.add_tool(sync_to_async(method))
            if tool.context_kwarg is None:
                forward_context = False
                tool.context_kwarg = "_context"
            else:
                forward_context = True
            tool.fn = _ToolsetMethodCaller(cls, name, tool.context_kwarg, forward_context)


global_mcp_server = DjangoMCP(**getattr(settings, 'DJANGO_MCP_GLOBAL_SERVER_CONFIG', {}))


class ToolsetMeta(type):
    registry = {}

    def __init__(cls, name, bases, namespace):
        super().__init__(name, bases, namespace)
        # Skip base class itself
        if name != "MCPToolset":
            ToolsetMeta.registry[name] = cls


class MCPToolset(metaclass=ToolsetMeta):
    """
    Base class for MCP toolsets. This class provides a way to create tools that can be used with
    the MCP server.
    """

    """You can define your own instance of DjangoMCP here """
    mcp_server : DjangoMCP = None

    def __init__(self, context=None):
        self.context = context
        if self.mcp_server is None:
            self.mcp_server = global_mcp_server


def init():
    for cls in ToolsetMeta.registry.values():
        (cls.mcp_server or global_mcp_server).register_mcptoolset_cls(cls)