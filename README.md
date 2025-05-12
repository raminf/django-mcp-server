# Django MCP Server

[![PyPI version](https://img.shields.io/pypi/v/django-mcp-server)](https://pypi.org/project/django-mcp-server/)
![License](https://img.shields.io/pypi/l/django-mcp-server)
[![Published on Django Packages](https://img.shields.io/badge/Published%20on-Django%20Packages-0c3c26)](https://djangopackages.org/packages/p/django-mcp-server/)
![Python versions](https://img.shields.io/pypi/pyversions/django-mcp-server)

**Django MCP Server** is an implementation of the **Model Context Protocol (MCP)** extension for Django. This module allows **MCP Clients** and **AI agents** to interact with **any Django application** seamlessly.

✅ Works inside your existing **WSGI** application.  
🚀 Implements the standare stdio and **Streamable HTTP transport (stateless)** is implemented. 
🤖 Any MCP Client, including Claude Desktop can interact with your application.

Licensed under the **MIT License**.

---

## Features

- Expose Django models and logic as **MCP tools**.
- Serve an MCP endpoint inside your Django app.
- Easily integrate with AI agents, MCP Clients, or tools like Google ADK.

---

## Quick Start

### 1️⃣ Install

```bash
pip install django-mcp-server
```

Or directly from GitHub:

```bash
pip install git+https://github.com/omarbenhamid/django-mcp-server.git
```

---

### 2️⃣ Configure Django

✅ Add `mcp_server` to your `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # your apps...
    'mcp_server',
]
```

✅ Add the **MCP endpoint** to your `urls.py`:

```python
from django.urls import path, include

urlpatterns = [
    # your urls...
    path("", include('mcp_server.urls')),
]
```

By default, the MCP endpoint will be available at `/mcp`.

---

### 3️⃣ Define MCP Tools

Create a file `mcp.py` in your Django app and create a sub class of MCPToolset : each method that does
not start with "_" will be published as a tool.

Example:
```python
from mcp_server import MCPToolset
from .models import Bird

class SpeciesCount(MCPToolset):
    # This method will not be published as a tool because it starts with _
    def _search_birds(self, search_string: str | None = None) -> Bird:
        """Get the queryset for birds,
        methods starting with _ are not registered as tools"""
        return Bird.objects.all() if search_string is None else Bird.objects.filter(species__icontains=search_string)

    def list_species(self, search_string: str = None) -> list[dict]:
        """List all species with a search string, returns the name and count of each species found"""
        return list(self._search_birds(search_string).values('species', 'count'))

    def increment_species(self, name: str, amount: int = 1) -> int:
        """
        Increment the count of a bird species by a specified amount and returns tehe new count.
        The first argument ios species name the second is the mouunt to increment with (1) by default.
        """
        ret = self._search_birds(name).first()
        if ret is None:
            ret = Bird.objects.create(species=name)

        ret.count += amount
        ret.save()

        return ret.count
```

---

### Use the MCP Tool

The mcp tool is now published on your Django App at `/mcp` endpoint. You can 
test it with the python mcp SDK :

```python
from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession


async def main():
    # Connect to a streamable HTTP server
    async with streamablehttp_client("http://localhost:8000/mcp") as (
        read_stream,
        write_stream,
        _,
    ):
        # Create a session using the client streams
        async with ClientSession(read_stream, write_stream) as session:
            # Initialize the connection
            await session.initialize()
            # Call a tool
            tool_result = await session.call_tool("get_alerts", {"state": "NY"})
            print(tool_result)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

Replace `http://localhost:8000/mcp` by the acutal Django host and run this cript.

### Test in Claude Desktop

You can [test MCP servers in Claude Desktop](https://modelcontextprotocol.io/quickstart/server). As for now
claude desktop only supports local MCP Servers. So you need to have your app installed on the same machine, in a
dev setting probably.

For this you need :

1. To install Claude Desktop from [claude.ai](https://claude.ai)
2. Open File > Settings > Developer and click **Edit Config**
3. Open `claude_desktop_config.json` and setup your MCP server :
   ```json
   {
    "mcpServers": {
        "test_django_mcp": {
            "command": "/path/to/interpreter/python",
            "args": [
                "/path/to/your/project/manage.py",
                "stdio_server"
            ]
        }
    }
   ```

**NOTE** `/path/to/interpreter/` should point to a python interpreter you use (can be in your venv for example)
and `/path/to/your/project/` is the path to your django project.


```python
{
    "mcpServers": {
        "gts": {
            "command": "C:/Progs/anaconda3/envs/i4/python.exe",
            "args": [
                "C:/Git/gts/i4server/manage.py",
                "stdio_server"
            ]
        }
    }
}
```


## Advanced topics

### Use low level mcp server annotation

You can import the DjangoMCP server instance and use FastMCP annotations to declare
mcp tools and resources :

```python
from mcp_server import mcp_server as mcp
from .models import Bird

print("Defining tools")

@mcp.tool()
async def get_species_count(name: str) -> int:
    '''Find the ID of a bird species by name (partial match). Returns the count.'''
    ret = await Bird.objects.filter(species__icontains=name).afirst()
    if ret is None:
        ret = await Bird.objects.acreate(species=name)
    return ret.count

@mcp.tool()
async def increment_species(name: str, amount: int = 1) -> int:
    '''
    Increment the count of a bird species by a specified amount.
    Returns the new count.
    '''
    ret = await Bird.objects.filter(species__icontains=name).afirst()
    if ret is None:
        ret = await Bird.objects.acreate(species=name)
    ret.count += amount
    await ret.asave()
    return ret.count
```

⚠️ **Important**: Always use **Django's async ORM API** in this case.

### Customize the default MCP server settings

In `settings.py` you can initialize the `DJANGO_MCP_GLOBAL_SERVER_CONFIG` parameter. These will be 
passed to the `MCPServer` server during initialization
```python
DJANGO_MCP_GLOBAL_SERVER_CONFIG = {
    "name":"mymcp",
    "instructions": "Some instructions to use this server"
}
```


### Authorization

Using [DRF annotations](https://www.django-rest-framework.org/api-guide/views/#api_view) you can enable authorization in urls.py :
```python
    path("mcp", api_view(['GET','POST'])(permission_classes([IsAuthenticated])(MCPServerStreamableHttpView.as_view())))
```

To conform to MCP specifications you should support OAuth2, so you should integrate for example 
[django-oauth-toolkit](https://github.com/jazzband/django-oauth-toolkit) for that.

### Secondary MCP endpoint
in `mcp.py`
```python

second_mcp = DjangoMCP(name="altserver")

@second_mcp.tools()
async def my_tool():
    ...
```

in urls.py 
```python
...
    path("altmcp", MCPServerStreamableHttpView.as_view(mcp_server=second_server))
...
```


## Testing

By default, your MCP Server will be available as a 
[stateless streamable http transport](https://modelcontextprotocol.io/specification/2025-03-26/basic/transports#streamable-http) 
endpoint at <your_django_server>/mcp (ex. http://localhost:8000/mcp) (*without / at the end !).

There are many ways to test :

1. Using the test [MCP Client script : test/test_mcp_client.py](test/test_mcp_client.py)  
2. You can test using [MCP Inspector tool](https://github.com/modelcontextprotocol/inspector) 
3. or any compatible MCP Client.

---

## Integration with Agentic Frameworks and MCP Clients

You can easily plug your MCP server endpoint into any agentic framework supporting MCP streamable http servers.
Refer to this [list of clients](https://modelcontextprotocol.io/clients)

---

## Roadmap

- ✅ **Stateless streamable HTTP transport** (implemented)
- 🔜 **STDIO transport integration for dev configuration (ex. Claude Desktop)**
- 🔜 ****
- 🔜 **Stateful streamable HTTP transport using Django sessions**
- 🔜 **SSE endpoint integration (requires ASGI)**
- 🔜 **Improved error management and logging**

---

## Issues

If you encounter bugs or have feature requests, please open an issue on [GitHub Issues](https://github.com/omarbenhamid/django-mcp-server/issues).

---

## License

MIT License.
