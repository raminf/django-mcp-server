# Django MCP Server

**Django MCP Server** is an implementation of the **Model Context Protocol (MCP)** extension for Django. This module allows **MCP Clients** and **AI agents** to interact with **any Django application** seamlessly.

✅ Works inside your existing **WSGI** application.  
🚀 **Streamable HTTP transport (stateless)** is implemented.  
🛣️ **Stateful transport** and **Server-Sent Events (SSE) responses** are on the roadmap (requires ASGI).  

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

Create a file `mcp.py` in your Django app.

Example:

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

⚠️ **Important**: Always use **Django's async ORM API**.

---

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
