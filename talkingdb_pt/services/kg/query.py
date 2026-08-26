from talkingdb_pt.services.kg.store import (
    OntologyBundle,
    node_properties,
    node_property,
    nodes_with_edge,
)

# Edge predicates are matched via the graph; anything else is treated as a
# scalar ontology_node_properties field. Kept as an explicit allowlist
# (rather than "anything registered as an edge") to keep filter behavior
# predictable as more predicates get registered.
_EDGE_FIELDS = {
    "instance_of",
    "subclass_of",
    "has_attributes",
    "has_units",
    "default_unit",
}

_COMPARATORS = {
    "eq": lambda a, b: a == b,
    "ge": lambda a, b: a is not None and a >= b,
    "gt": lambda a, b: a is not None and a > b,
    "le": lambda a, b: a is not None and a <= b,
    "lt": lambda a, b: a is not None and a < b,
    "in": lambda a, b: a in b,
}

DEFAULT_FIELDS = [
    "src_name",
    "contains",
    "pt_prec",
    "range_min",
    "range_max",
    "multiplier",
    "shorthands",
    "src_url",
    "is_a",
]


def _base_instance_ids(bundle: OntologyBundle) -> set[str]:
    """Legacy's base query was func: has(instance_of) - every node that is
    itself an instance of something (excludes bare class/type nodes)."""

    return {edge["source"] for edge in nodes_with_edge(bundle, "instance_of")}


def _matches_clause(bundle: OntologyBundle, node_id: str, clause: dict) -> bool:
    field = clause["field"]
    op = clause.get("op", "eq")
    value = clause["value"]

    if field in _EDGE_FIELDS:
        # Only set-membership makes sense for an edge (ge/gt/le/lt don't
        # apply to a target node_id): "eq" means value is one of the
        # targets, "in" means any of a list of values overlaps them.
        targets = {
            edge["target"]
            for edge in nodes_with_edge(bundle, field, source_ids=[node_id])
        }
        if op == "in":
            return bool(targets & set(value))
        return value in targets

    actual = node_property(bundle, node_id, field)
    return _COMPARATORS[op](actual, value)


def _project(bundle: OntologyBundle, node_id: str, fields: list[str] | None) -> dict:
    result = {
        "node_id": node_id,
        "label": bundle.graph.nodes[node_id].get("label"),
        "surface_texts": list(bundle.graph.nodes[node_id].get("surface_texts", [])),
    }
    result.update(node_properties(bundle, node_id, fields or DEFAULT_FIELDS))
    return result


def run_filter_query(
    bundle: OntologyBundle,
    filters: list[dict] | None = None,
    sorters: list[dict] | None = None,
    limit: int = 20,
    offset: int = 0,
    fields: list[str] | None = None,
) -> list[dict]:
    """Structured replacement for the legacy find_instances_v2, which took
    a raw Dgraph DQL filter expression string - there's no 1:1 SQLite
    equivalent for that, so this is a genuine redesign: a flat list of
    AND-combined filter clauses instead of an arbitrary query-language
    string. All filters are ANDed (no OR/NOT support in this first
    version - can be extended if a real use case needs it)."""

    if limit <= 0:
        raise ValueError("limit must be greater than zero")

    candidates = _base_instance_ids(bundle)
    for clause in filters or []:
        candidates = {
            node_id
            for node_id in candidates
            if _matches_clause(bundle, node_id, clause)
        }

    results = [_project(bundle, node_id, fields) for node_id in candidates]

    for sorter in reversed(sorters or []):
        field = sorter["field"]
        reverse = sorter.get("direction", "asc") == "desc"
        results.sort(
            key=lambda r: (r.get(field) is None, r.get(field)), reverse=reverse
        )

    return results[offset : offset + limit]


def run_multiple_filter_queries(
    bundle: OntologyBundle, queries: list[dict]
) -> list[dict]:
    return [
        {"filter": query, "results": run_filter_query(bundle, **query)}
        for query in queries
    ]


def list_entity_synonyms(bundle: OntologyBundle, limit: int) -> list[dict]:
    """Replaces the legacy Mongo kg_data-backed get_synonyms_for_kg_entities
    - alternate_names now map directly onto EntityModel.surface_texts, so
    this is a plain graph-node listing instead of a side-index read."""

    results = []
    for entity in bundle.tenant.iter_entities():
        if len(results) >= limit:
            break
        results.append(
            {
                "node_id": entity["id"],
                "src_id": entity["id"],
                "alternate_names": entity["surface_texts"],
            }
        )
    return results
