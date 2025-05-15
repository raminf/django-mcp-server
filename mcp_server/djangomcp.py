import contextvars
import functools
import inspect
from collections import defaultdict
from functools import cached_property
from importlib import import_module

import anyio
from asgiref.sync import sync_to_async
from django.conf import settings
from django.db.models import QuerySet, Model, TextField, CharField
from mcp.server import FastMCP, Server
from mcp.server.fastmcp import Context
from mcp.server.sse import SseServerTransport
from mcp.server.streamable_http import StreamableHTTPServerTransport
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

from django.http import HttpResponse, HttpRequest
from asgiref.compatibility import guarantee_single_callable
from asgiref.wsgi import WsgiToAsgi
from mcp.types import AnyFunction, ToolAnnotations
from rest_framework.serializers import Serializer
from starlette.types import Scope, Receive, Send
from starlette.datastructures import Headers
from io import BytesIO
import asyncio

from mcp_server.agg_pipeline_ql import apply_json_mango_query, pipeline_dsl_spec, generate_json_schema

django_request_ctx = contextvars.ContextVar("django_request")


def drf_serialize_output(serializer_class: type[Serializer]):
    """
    This annotation will process the tool result thorugh the given DRF serializer

    ```
    @drf_serialize_output(MyDRFSerializer)
    def my_function(args):
        return MyInstance()
    ```


    :param serializer_class:
    :return:
    """
    def annotator(fn):
        fn.__dmcp_drf_serializer = serializer_class
        return fn
    return annotator


class _SyncToolCallWrapper:
    def __init__(self, fn):
        self.fn = fn
        functools.update_wrapper(self, fn)

    def __call__(self, *args, **kwargs):
        ret = self.fn(*args, **kwargs)
        if isinstance(ret, QuerySet):
            ret = list(ret)
        serializer_class = getattr(self.fn, '__dmcp_drf_serializer', None)
        if serializer_class is not None:
             ret = serializer_class(ret).data
        return ret


async def _call_starlette_handler(django_request: HttpRequest, session_manager: StreamableHTTPSessionManager):
    """
    Adapts a Django request into a Starlette request and calls session_manager.handle_request.

    Returns:
        A Django HttpResponse
    """
    django_request_ctx.set(django_request)
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
        instance = self.class_(context=kwargs[self.context_kwarg],
                               request=django_request_ctx.get())
        # Get the method
        method = sync_to_async(_SyncToolCallWrapper(getattr(instance, self.method_name)))
        if not self.forward_context_kwarg:
            # Remove the context kwarg from kwargs
            del kwargs[self.context_kwarg]

        return method(*args, **kwargs)


MCP_SESSION_ID_HDR="Mcp-Session-Id"


# FIXME: shall I reimplement the necessary without the
# Stuff pulled to support embedded server ?
class DjangoMCP(FastMCP):

    def __init__(self, name=None, instructions=None, stateless=False):
        # Prevent extra server settings as we do not use the embedded server
        super().__init__(name or "django_mcp_server", instructions)
        self.stateless=stateless
        engine = import_module(settings.SESSION_ENGINE)
        self.SessionStore = engine.SessionStore

    @property
    def session_manager(self) -> StreamableHTTPSessionManager:
        return StreamableHTTPSessionManager(
            app=self._mcp_server,
            event_store=self._event_store,
            json_response=True,
            stateless=True,  # Sessions will be managed as Django sessions.
        )

    def handle_django_request(self, request):
        """
        Handle a Django request and return a response.
        This method is called by the Django view when a request is received.
        """
        if not self.stateless:
            session_key = request.headers.get(MCP_SESSION_ID_HDR)
            if session_key:
                session = self.SessionStore(session_key)
                if session.exists(session_key):
                    request.session = session
                else:
                    return HttpResponse(status=404, content="Session not found")
            elif request.body and request.data.get('method') == 'initialize':
                # FIXME: Trick to read body before data to avoid DRF complaining
                request.session = self.SessionStore()
            else:
                return HttpResponse(status=400, content="Session required for stateful server")

        result = anyio.run(_call_starlette_handler, request, self.session_manager)
        request.session.save()
        result.headers[MCP_SESSION_ID_HDR]=request.session.session_key
        delattr(request, 'session')

        return result

    def destroy_session(self, request):
        session_key = request.headers.get(MCP_SESSION_ID_HDR)
        if not self.stateless and session_key:
            self.SessionStore(session_key).flush()
            request.session = None

    def register_mcptoolset_cls(self, cls):
        cls()._add_tools_to(self._tool_manager)


global_mcp_server = DjangoMCP(**getattr(settings, 'DJANGO_MCP_GLOBAL_SERVER_CONFIG', {}))


class ToolsetMeta(type):
    registry = {}

    def __init__(cls, name, bases, namespace):
        super().__init__(name, bases, namespace)
        # Skip base class itself
        if name not in ("ModelQueryToolset", "MCPToolset"):
            ToolsetMeta.registry[name] = cls


class MCPToolset(metaclass=ToolsetMeta):
    """
    Base class for MCP toolsets. This class provides a way to create tools that can be used with
    the built in MCP serfver in a declarative way.

    ```
    class MyAppTools(MCPToolset):
        def my_tool(param : Type) -> ReturnType:
            ...
    ```

    Any "private" method (ie. its name starting with _) will not be declared as a tool.
    Any other method is published as an MCP Tool that MCP Clients can use.

    During tool execution, self.request contains the origin django request, this allows for example
    access to request.user ...

    """

    """You can define your own instance of DjangoMCP here """
    mcp_server: DjangoMCP = None

    def __init__(self, context=None, request=None):
        self.context = context
        self.request = request
        if self.mcp_server is None:
            self.mcp_server = global_mcp_server

    def _add_tools_to(self, tool_manager):
        # ITerate all the methods whose name does not start with _ and register them with mcp_server.add_tool
        for name, method in inspect.getmembers(self, predicate=inspect.ismethod):
            if not callable(method) or name.startswith("_"): continue
            tool = tool_manager.add_tool(sync_to_async(method))
            if tool.context_kwarg is None:
                forward_context = False
                tool.context_kwarg = "_context"
            else:
                forward_context = True
            tool.fn = _ToolsetMethodCaller(self.__class__, name, tool.context_kwarg, forward_context)


class ModelQueryToolset(metaclass=ToolsetMeta):
    mcp_server: DjangoMCP = None
    "The server to use, if not set, the global one will be used."

    model: type(Model) = None
    " The model to query, this is used to generate the JSON schema and the query methods. "

    name: str = None
    "The name of the tool, if not set, the class name will be used "

    extra_published_models: list[Model] = []
    "The list of models allowed to query or navigate in addition to the main one as foreign keys for example."

    exclude_fields: dict[type(Model), str] = {}
    "A dict mapping Model classes to fields that must not be in schema: the main model or published models"

    fields: dict[type(Model), str] = {}
    "A dict mapping Model classes to the only fields that can be in schema: for the main model or published models"

    search_fields: list[str] = None
    "List of fields for full text search, if not set it defaults to textual fields allowed by 'fields' parameters."

    extra_filters: list[str] = None
    "A list of queryset api filters that will be accessible to the MCP client for querying."

    extra_instructions: str = None
    "Extra instruction to provide to the MCP client (usually the agent)"


    @cached_property
    def _text_search_fields(self):
        if self.search_fields is not None:
            return self.search_fields
        fields = self.fields.get(self.model)
        if fields is None:
            return [f.name for f in self.model._meta.get_fields() if
                          isinstance(f, (CharField, TextField)) and f.concrete and not f.is_relation]
        else:
            return [f for f in fields if not self.model._meta.fields[f].is_relation and
                                  isinstance(self.model._meta.fields[f], (CharField, TextField))]


    def get_queryset(self):
        """ Return the queryset, override to customize"""
        return self.model._default_manager.all()

    def get_instructions(self):
        """ Generates the instructions, you can add extra instructions with the
        extra_instructions attribute. Doc string of the class is included if set"""
        instructions = self.__doc__ or f"A tool to query '{self.model._meta.model_name}' collection"
        ret = f"""{instructions}.
{pipeline_dsl_spec(bool(self._text_search_fields))}

# JSON schemas involved:

## {self.model._meta.model_name} (the main queried collection)
```json
{generate_json_schema(self.model, fields=self.fields.get(self.model),
                      exclude=self.exclude_fields.get(self.model))}
```
"""

        for model in self.extra_published_models:
            ret += f"""
## {model._meta.model_name}
```json
{generate_json_schema(model, fields=self.fields.get(model),
                      exclude=self.exclude_fields.get(model))}
```
"""
            if self.extra_instructions:
                ret += f"""
# Extra instructions

{self.extra_instructions}

"""
        return ret

    def query(self, search_pipeline: list[dict] = None) -> list[dict]:
        qs = self.get_queryset()

        return list(apply_json_mango_query(qs, search_pipeline,
                                           text_search_fields=self._text_search_fields,
                                           allowed_models=[self.model, *self.extra_published_models],
                                           extended_operators=self.extra_filters))

    def __init__(self, context=None, request=None):
        self.context = context
        self.request = request
        if self.mcp_server is None:
            self.mcp_server = global_mcp_server

    def _add_tools_to(self, tool_manager):
        # ITerate all the methods whose name does not start with _ and register them with mcp_server.add_tool
        method = self.query
        name = self.name or f"{self.__class__.__name__}_{self.model._meta.model_name}Query"

        tool = tool_manager.add_tool(
            fn=sync_to_async(method),
            name=name,
            description=self.get_instructions()
        )

        tool.context_kwarg = "_context"
        tool.fn = _ToolsetMethodCaller(self.__class__, "query", "_context", False)


def init():
    for cls in ToolsetMeta.registry.values():
        (cls.mcp_server or global_mcp_server).register_mcptoolset_cls(cls)