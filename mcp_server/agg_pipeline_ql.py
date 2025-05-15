from django.db import models
from django.db.models import Q, QuerySet
from collections import defaultdict

"""
    Tools to generate MongoDB-style $jsonSchema from Django models
    and to apply JSON-like queries to Django QuerySets using a subset 
    of MangoDB aggregation pipeline syntax.
"""


def generate_json_schema(model, fields=None, exclude=None):
    """
    Generate a MongoDB-style $jsonSchema from a Django model.

    Args:
        model: Django model class
        fields: Optional list of field names to include
        exclude: Optional list of field names to exclude

    Returns:
        A dict representing the $jsonSchema
    """

    type_mapping = {
        models.CharField: "string",
        models.TextField: "string",
        models.IntegerField: "int",
        models.FloatField: "double",
        models.BooleanField: "bool",
        models.DateTimeField: "date",
        models.DateField: "date",
        models.TimeField: "string",
        models.EmailField: "string",
        models.URLField: "string",
        models.DecimalField: "double",
        models.AutoField: "int",
        models.BigAutoField: "long",
        models.BigIntegerField: "long",
        models.JSONField: "object",
    }

    schema = {
        "description": (model.__doc__ or "").strip(),
        "$jsonSchema": {
            "bsonType": "object",
            "properties": {},
            "required": []
        }
    }

    for field in model._meta.get_fields():
        if field.auto_created or not field.concrete:
            continue
        if fields and field.name not in fields:
            continue
        if exclude and field.name in exclude:
            continue

        prop = {}

        # Primary key description
        if getattr(field, 'primary_key', False):
            prop["description"] = "Primary unique identifier for this model"

        # ForeignKey
        if isinstance(field, models.ForeignKey):
            prop["bsonType"] = "objectId"
            prop["description"] = f"Reference to {field.related_model.__name__}"
            if field.help_text:
                prop["description"] += ": " + str(field.help_text)
            prop["ref"] = field.related_model.__name__
        else:
            # Type detection
            for django_type, bson_type in type_mapping.items():
                if isinstance(field, django_type):
                    prop["bsonType"] = bson_type
                    break
            else:
                prop["bsonType"] = "string"

            # Regular field description
            if field.help_text:
                prop["description"] = field.help_text
            if field.choices:
                # Add enum values
                prop["enum"] = [choice[0] for choice in field.choices]

                # Build display labels
                choice_desc = ", ".join(f"{repr(val)} = {label}" for val, label in field.choices)

                # Append to existing or new description
                if "description" in prop:
                    prop["description"] += f" Choices: {choice_desc}"
                else:
                    prop["description"] = f"Choices: {choice_desc}"

        schema["$jsonSchema"]["properties"][field.name] = prop

        if not getattr(field, 'null', True) and not getattr(field, 'blank', True):
            schema["$jsonSchema"]["required"].append(field.name)

    if not schema["$jsonSchema"]["required"]:
        del schema["$jsonSchema"]["required"]

    return schema



PIPELINE_DSL_SPEC ="""
The syntax to query is a subset of MangoDB aggregation pipeline JSON with support of following stages : 

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
5. $project: Selects specific fields for results. Only "flat" objects are supported.
   Value is either a number/boolean to include/exclude the field or a string starting in format 
   "$<lookupAlias>.<field>" to project a field from a previous $lookup stage.  
"""


def apply_json_mango_query(queryset: QuerySet, pipeline: list[dict],
                           allowed_models: list = None, extended_operators: list = None):
    """
    Apply a JSON-like query to a Django QuerySet using a subset of MangoDB aggregation pipeline syntax.
    see PIPELINE_DSL_SPEC for details.
    :param queryset: The base queryset to query
    :param pipeline: a list of stages to apply to the queryset compliant with PIPELINE_DSL_SPEC
    :param allowed_models: List of allowed models for $lookup stages. If None, all models are allowed. Can be the string name or the Model class.
    :param extended_operators: List of Queryset API lookups to support as exetended operators. this interprets {"<field>":{"$<op>": value} as Q({field}__{op}=value)
    :return: an iterable (eventually the queryset) of JSON results.
    """
    if extended_operators is None:
        extended_operators = []

    if allowed_models:
        allowed_models = [model.lower() if isinstance(model, str) else model._meta.model_name.lower()  for model in allowed_models]

    model = queryset.model
    model_name = model._meta.model_name

    lookup_alias_map = {}

    # First pass: Apply lookups
    for stage in pipeline:
        if "$lookup" in stage:
            lookup = stage["$lookup"]
            _validate_lookup(model, lookup, allowed_models, lookup_alias_map)
            as_field = lookup["as"]
            local_field = _translate_field(lookup["localField"], lookup_alias_map)
            foreign_field = lookup["foreignField"]
            lookup_alias_map[as_field] = {
                "prefix": local_field.replace("_id", ""),
                "foreign_field": foreign_field
            }

    # Second pass: Apply rest
    projection_fields = None
    projection_mapping = None
    skip_value = None

    for stage in pipeline:
        if "$match" in stage:
            queryset = queryset.filter(_parse_match(stage["$match"], extended_operators, lookup_alias_map))
        elif "$sort" in stage:
            order = []
            for field, direction in stage["$sort"].items():
                order.append(field if direction == 1 else f"-{field}")
            queryset = queryset.order_by(*order)
        elif "$skip" in stage:
            skip_value = stage["$skip"]
        elif "$limit" in stage:
            queryset = queryset[:stage["$limit"]]
        elif "$project" in stage:
            projection_fields, projection_mapping = _interpret_projection(stage["$project"], lookup_alias_map)

    if skip_value is not None:
        queryset = queryset[skip_value:]

    if projection_fields:
        queryset = queryset.values(*projection_fields)
        return _postprocess_projection(queryset, projection_mapping)

    return _postprocess_projection(queryset.values(), None)


def _interpret_projection(projection, lookup_map):
    fields = []
    mapping = {}
    for output_field, spec in projection.items():
        if isinstance(spec, str) and spec.startswith("$"):
            path = spec[1:]
            if path == "_id":
                path = "pk"
            internal_field = _translate_field(path, lookup_map)
            fields.append(internal_field)
            mapping[output_field] = internal_field
        elif spec:
            path = output_field if output_field != "_id" else "pk"
            internal_field = _translate_field(path, lookup_map)
            fields.append(internal_field)
            mapping[output_field] = internal_field
    return fields, mapping


def _postprocess_projection(queryset, projection_mapping):
    if not projection_mapping:
        yield from queryset
        return

    for row in queryset:
        result = {}
        for key, internal_key in projection_mapping.items():
            value = row.get(internal_key)
            _assign_nested_value(result, key.split("."), value)
        yield result


def _assign_nested_value(target, path_parts, value):
    for part in path_parts[:-1]:
        target = target.setdefault(part, {})
    target[path_parts[-1]] = value


def _restore_field_path(field, lookup_map):
    for alias, info in lookup_map.items():
        prefix = info['prefix']
        if field.startswith(prefix + "__"):
            return alias + "." + field[len(prefix + "__"):].replace("__", ".")
    return field.replace("__", ".")


def _validate_lookup(model, lookup, allowed_models, lookup_map):
    from_model_name = lookup["from"]
    if allowed_models is not None and from_model_name.lower() not in allowed_models:
        raise ValueError(f"Lookup from model '{from_model_name}' is not allowed.")

    local_field_name = _translate_field(lookup["localField"], lookup_map)
    foreign_field_name = lookup["foreignField"]

    base_model, field_name = _resolve_model_from_path(model, local_field_name, lookup_map)

    try:
        local_field = base_model._meta.get_field(field_name)
    except Exception:
        raise ValueError(f"Field '{field_name}' does not exist in model '{base_model.__name__}'.")

    if not local_field.is_relation or not local_field.many_to_one:
        raise ValueError(f"Field '{field_name}' is not a ForeignKey.")

    related_model = local_field.related_model
    if foreign_field_name != related_model._meta.pk.name and foreign_field_name != "_id":
        raise ValueError(f"Foreign field '{foreign_field_name}' is not the primary key of model '{from_model_name}'.")


def _resolve_model_from_path(model, field_path, lookup_map):
    parts = field_path.split("__")
    current_model = model
    for part in parts[:-1]:
        try:
            field = current_model._meta.get_field(part)
            if field.is_relation:
                current_model = field.related_model
            else:
                break
        except Exception:
            raise ValueError(f"Invalid field path '{field_path}' at '{part}' in model '{current_model.__name__}'.")
    return current_model, parts[-1]


def _parse_match(match, extended_operators, lookup_map):
    if "$and" in match:
        return Q(*[_parse_match(cond, extended_operators, lookup_map) for cond in match["$and"]])
    if "$or" in match:
        return Q(*[_parse_match(cond, extended_operators, lookup_map) for cond in match["$or"]], _connector=Q.OR)
    if "$nor" in match:
        return ~Q(*[_parse_match(cond, extended_operators, lookup_map) for cond in match["$nor"]], _connector=Q.OR)

    q = Q()
    for field, condition in match.items():
        field = _translate_field(field, lookup_map)

        if isinstance(condition, dict):
            for op, value in condition.items():
                if op.startswith("$"):
                    op_name = op[1:]
                    if op_name in ["eq", "ne", "gt", "gte", "lt", "lte", "in", "nin"]:
                        django_op = "" if op_name == "eq" else f"__{op_name}"
                        key = f"{field}{django_op}"
                    elif op_name == "regex":
                        key = f"{field}__regex"
                    elif op_name in extended_operators:
                        key = f"{field}__{op_name}"
                    else:
                        raise ValueError(f"Unsupported operator: {op}")
                    q &= Q(**{key: value})
                else:
                    raise ValueError(f"Unknown match key: {op}")
        else:
            q &= Q(**{field: condition})
    return q


def _translate_field(field, lookup_map):
    if field == "_id":
        return "pk"
    if "." in field:
        alias, rest = field.split(".", 1)
        if alias in lookup_map:
            return f"{lookup_map[alias]['prefix']}__{rest}"
        else:
            raise ValueError(f"Unknown lookup alias '{alias}', ensure it appears in the 'as' field of a previous $lookup")
    return field
