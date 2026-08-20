from talkingdb_pt.services.kg.store import OntologyBundle, save as save_bundle
from talkingdb_pt.services.kg.store import upsert_edge, upsert_node
from talkingdb_pt.services.ontology import naming
from talkingdb_pt.services.ontology.store import (
    find_ontology_type,
    list_ontology_types,
    upsert_ontology_type,
)

# Well-known edge predicates every registered type gets for free - matches
# the legacy Dgraph schema's default REF attributes (kg_class_type_def_attr_schema
# / kg_instance_type_def_attr_schema). Anything else is an edge only if the
# node's own registered type declared it as such via extra_attrs.
_BUILTIN_EDGE_PREDICATES = {
    "subclass_of": {"list": False},
    "instance_of": {"list": True},
}

# Recognized scalar columns on ontology_node_properties. Anything else scalar
# falls into extra_json.
_KNOWN_SCALAR_FIELDS = {
    "src_name",
    "contains",
    "pt_prec",
    "range_min",
    "range_max",
    "multiplier",
    "shorthands",
    "src_url",
    "is_a",
}

_RESERVED_KEYS = {"src_id", "alternate_names", "class_type", "instance_type", "type_name"}


class OntologyTrainerError(Exception):
    """Raised for any ontology-write failure that should surface as a 4xx."""


def add_type_to_ontology(
    conn,
    namespace: str,
    type_name: str,
    create_class: bool,
    create_instance: bool,
    extra_attrs: dict | None = None,
    relationship_triples: list[list[str]] | None = None,
    metadata: dict | None = None,
) -> str:
    extra_attrs = extra_attrs or {}
    metadata = metadata or {}
    relationship_triples = relationship_triples or []

    kg_type_name = (
        naming.class_type_name(type_name)
        if create_class
        else naming.instance_type_name(type_name)
    )

    resolved_triples = []
    for predicate, target_type in (
        (rt[0], rt[1]) for rt in relationship_triples
    ):
        target_kg_type_name = (
            naming.class_type_name(target_type)
            if predicate in ("instance_of", "subclass_of")
            else naming.instance_type_name(target_type)
        )
        resolved_triples.append([kg_type_name, predicate, target_kg_type_name])

    upsert_ontology_type(
        conn,
        namespace=namespace,
        kg_type_name=kg_type_name,
        type_name=type_name,
        is_class=create_class,
        is_instance=create_instance,
        class_type_group=metadata.get("class_type"),
        instance_type_group=metadata.get("instance_type"),
        extra_attrs=extra_attrs,
        relationship_triples=resolved_triples,
    )

    return kg_type_name


def view_ontology_types(conn, namespace: str) -> list[dict]:
    return list_ontology_types(conn, namespace)


def _resolve_node_type(conn, namespace: str, node_data: dict) -> dict:
    if "class_type" in node_data:
        group, data_type = node_data["class_type"], "class_type_group"
    elif "instance_type" in node_data:
        group, data_type = node_data["instance_type"], "instance_type_group"
    else:
        raise OntologyTrainerError(
            "node data must include either 'class_type' or 'instance_type'"
        )

    ontology_type = find_ontology_type(
        conn,
        namespace,
        group=group,
        data_type=data_type,
        type_name=node_data.get("type_name"),
    )

    if ontology_type is None:
        raise OntologyTrainerError(
            f"no ontology type registered for {data_type}={group!r} "
            f"in namespace {namespace!r} (or universal)"
        )

    return ontology_type


def _edge_spec(ontology_type: dict, key: str) -> dict | None:
    if key in _BUILTIN_EDGE_PREDICATES:
        return _BUILTIN_EDGE_PREDICATES[key]

    attr = ontology_type["extra_attrs"].get(key)
    if not attr:
        return None

    value_type = attr.get("value_type")
    if value_type == "REF":
        return {"list": False}
    if value_type == "[REF]":
        return {"list": True}

    return None


def add_node_to_kg(bundle: OntologyBundle, node_data: dict) -> str:
    """
    Write one node (and any edges declared on it) into the ontology.
    Replaces the legacy add_data_to_kg's per-node Dgraph upsert-and-get-uid
    dance: node_id == src_id directly, no uid resolution round-trip needed.
    """

    conn = bundle.entity_conn
    namespace = bundle.namespace

    node_data = dict(node_data)
    src_id = node_data.pop("src_id", None)
    if not src_id:
        raise OntologyTrainerError("node data must include 'src_id'")

    ontology_type = _resolve_node_type(conn, namespace, node_data)
    node_data.pop("class_type", None)
    node_data.pop("instance_type", None)
    node_data.pop("type_name", None)

    alternate_names = node_data.pop("alternate_names", [])

    scalar_props: dict = {}
    edges: list[tuple[str, str]] = []  # (predicate, target_node_id)

    for key, value in node_data.items():
        edge_spec = _edge_spec(ontology_type, key)

        if edge_spec is not None:
            targets = value if edge_spec["list"] else [value]
            edges.extend((key, target) for target in targets)
            continue

        if key in _KNOWN_SCALAR_FIELDS:
            scalar_props[key] = value
        else:
            scalar_props.setdefault("extra_json", {})[key] = value

    upsert_node(
        bundle,
        src_id,
        label=ontology_type["kg_type_name"],
        surface_texts=alternate_names,
        scalar_props=scalar_props or None,
    )

    for predicate, target_node_id in edges:
        if not bundle.graph.has_node(target_node_id):
            raise OntologyTrainerError(
                f"edge target {target_node_id!r} for predicate {predicate!r} "
                f"does not exist (node_id == src_id; create the target node first)"
            )

        upsert_edge(bundle, src_id, predicate, target_node_id)

    return src_id


def add_data_to_kg(bundle: OntologyBundle, nodes_data: list[dict]) -> list[str]:
    node_ids = [add_node_to_kg(bundle, node_data) for node_data in nodes_data]
    save_bundle(bundle)
    return node_ids


def get_nodes_number_trained(bundle: OntologyBundle) -> int:
    return bundle.tenant.graph.number_of_nodes()
