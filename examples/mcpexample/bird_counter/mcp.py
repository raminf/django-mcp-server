from rest_framework.serializers import ModelSerializer

from mcp_server import MCPToolset, drf_serialize_output, agg_pipeline_ql
from .models import Bird, Location, City
from .serializers import BirdSerializer


class SpeciesCount(MCPToolset):
    def _search_birds(self, search_string: str | None = None) -> Bird:
        """Get the queryset for birds,
        methods starting with _ are not registered as tools"""
        return Bird.objects.all() if search_string is None else Bird.objects.filter(species__icontains=search_string)

    def query_species(self, search_pipeline: list[dict] = None) -> list[dict]:
        # Returning a queryset is ok as we auto convert it to a lsit
        ret = agg_pipeline_ql.apply_json_mango_query(Bird.objects.all(), search_pipeline)
        return list(ret)

    query_species.__doc__ = f"""Query 'bird' collection.
{agg_pipeline_ql.PIPELINE_DSL_SPEC}

# JSON schemas involved:
## bird
```json
{agg_pipeline_ql.generate_json_schema(Bird)}
```

## location
```json
{agg_pipeline_ql.generate_json_schema(Location)}
```

## city
```json
{agg_pipeline_ql.generate_json_schema(City)}
```
"""

    @drf_serialize_output(BirdSerializer)
    def increment_species(self, name: str, amount: int = 1):
        """
        Increment the count of a bird species by a specified amount and returns tehe new count.
        The first argument ios species name the second is the mouunt to increment with (1) by default.
        """
        ret = self._search_birds(name).first()
        if ret is None:
            ret = Bird.objects.create(species=name)

        ret.count += amount
        ret.save()

        return ret

# For more advanced low level usage, you can use the mcp_server directly
from mcp_server import mcp_server as mcp

@mcp.tool()
async def get_species_count(name : str):
    """ Find the ID of a bird species by its name or part of name. Returns the count"""
    ret = await Bird.objects.filter(species__icontains=name).afirst()
    if ret is None:
        ret = await Bird.objects.acreate(species=name)

    return ret.count


##

