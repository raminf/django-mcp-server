from mcp.server import FastMCP

from mcp_server import mcp_server as mcp
from .models import Bird


print("Defining tools")


@mcp.tool()
async def get_species_count(name : str) -> int:
    """ Find the ID of a bird species by its name or part of name. Returns the count"""
    ret = await Bird.objects.filter(species__icontains=name).afirst()
    if ret is None:
        ret = await Bird.objects.acreate(species=name)

    return ret.count

@mcp.tool()
async def increment_species(name : str, amount: int = 1) -> int:
    """
    Increment the count of a bird species by a specified amount and returns tehe new count.
    The first argument ios species name the second is the mouunt to increment with (1) by default.
    """
    ret = await Bird.objects.filter(species__icontains=name).afirst()
    if ret is None:
        ret = await Bird.objects.acreate(species=name)

    ret.count += amount
    await ret.asave()

    return ret.count