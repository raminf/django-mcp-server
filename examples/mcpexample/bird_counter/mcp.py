from rest_framework.serializers import ModelSerializer

from mcp_server import MCPToolset, drf_serialize_output, jsonql
from .models import Bird, Location, City
from .serializers import BirdSerializer


class SpeciesCount(MCPToolset):
    def _search_birds(self, search_string: str | None = None) -> Bird:
        """Get the queryset for birds,
        methods starting with _ are not registered as tools"""
        return Bird.objects.all() if search_string is None else Bird.objects.filter(species__icontains=search_string)

    def query_species(self, search_pipeline: list[dict] = None) -> list[dict]:
        # Returning a queryset is ok as we auto convert it to a lsit
        qs = jsonql.apply_json_mango_query(Bird.objects.all(), search_pipeline)
        return  qs.values('species', 'count')

    query_species.__doc__ = f"""Query 'bird' collection using MongoDB aggregation pipeline syntax.
# Supported pipeline stages and operators

1. $lookup: Joins another collection :.
  - "from" must refer to a model name listed in ref in the schema (if defined).
  - "localField" must be a field path on the base colletion or a previous $lookup alias.
  - "foreignField" must be "_id"
  - "as" defines an alias used in subsequent $match and $lookup stages as a prefix (e.g., alias.field).
2. $match: Filter documents using comparison and logical operators.
  - Supports: $eq, $ne, $gt, $gte, $lt, $lte, $in, $nin, $regex
  - Field references can include lookup aliases via dot notation, e.g. "user.name"
3. $sort: Sorts the result. Keys must map to model fields.
4. $limit: Truncates the result set to the specified number of items.
5. $project: Selects specific fields for results.

# JSON schemas involved:
## bird
```json
{jsonql.generate_json_schema(Bird)}
```

## location
```json
{jsonql.generate_json_schema(Location)}
```


## city
```json
{jsonql.generate_json_schema(City)}
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

