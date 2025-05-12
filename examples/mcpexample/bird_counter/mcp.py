from mcp_server import MCPToolset
from .models import Bird


class SpeciesCount(MCPToolset):
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

# For more advanced low level usage, you can use the mcp_server directly
from mcp_server import mcp_server as mcp

@mcp.tool()
async def get_species_count(name : str) -> int:
    """ Find the ID of a bird species by its name or part of name. Returns the count"""
    ret = await Bird.objects.filter(species__icontains=name).afirst()
    if ret is None:
        ret = await Bird.objects.acreate(species=name)

    return ret.count

