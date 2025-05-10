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

You can test your MCP server using any **MCP Inspector tool** or a compatible MCP Client.

---

## Integration with Google ADK Agent

You can easily plug your MCP server endpoint into a **Google ADK agent** or similar MCP-compatible AI clients.

---

## Roadmap

- ✅ **Stateless streamable HTTP transport** (implemented)
- 🔜 **Stateful transport using Django sessions**
- 🔜 **SSE endpoint integration (requires ASGI)**
- 🔜 **Improved error management and logging**
- 🔜 **Publish on PyPI and list on Awesome MCP / Django modules**

---

## Issues

If you encounter bugs or have feature requests, please open an issue on [GitHub Issues](https://github.com/omarbenhamid/django-mcp-server/issues).

---

## License

MIT License.
