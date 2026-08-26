from __future__ import annotations

import sqlite3
from dataclasses import dataclass

import networkx as nx
from talkingdb.models.entity.entity import EntityModel

from talkingdb_pt.services.entity.base import entity_conn
from talkingdb_pt.services.ontology import store as ontology_store

UNIVERSAL_NAMESPACE = ontology_store.UNIVERSAL_NAMESPACE


def _entity_id(namespace: str) -> str:
    return EntityModel.make_id(f"ontology::{namespace}")


@dataclass
class OntologyBundle:
    namespace: str
    universal: EntityModel
    tenant: EntityModel
    graph: nx.MultiDiGraph
    entity_conn: sqlite3.Connection
    # Cache slot for the literal-attribute lookup maps (talkingdb_pt.services
    # .parsing.literal_maps) - expensive to rebuild per-request, invalidated
    # whenever this bundle is saved. Not populated here to avoid a circular
    # import; parsing.literal_maps owns writing to it.
    literal_maps: object = None

    def refresh_graph(self) -> None:
        # nx.compose(G, H): H's node/edge attributes win on collision, so
        # composing (universal, tenant) lets a tenant-specific node/edge
        # override the shared universal definition.
        self.graph = nx.compose(self.universal.graph, self.tenant.graph)


def _build_bundle(namespace: str) -> OntologyBundle:
    universal = EntityModel.load(
        conn=entity_conn,
        entity_id=_entity_id(UNIVERSAL_NAMESPACE),
    )

    tenant = (
        universal
        if namespace == UNIVERSAL_NAMESPACE
        else EntityModel.load(conn=entity_conn, entity_id=_entity_id(namespace))
    )

    bundle = OntologyBundle(
        namespace=namespace,
        universal=universal,
        tenant=tenant,
        graph=nx.MultiDiGraph(),
        entity_conn=entity_conn,
    )
    bundle.refresh_graph()
    return bundle


class OntologyRegistry:
    """Lazily loads and caches one OntologyBundle per namespace."""

    def __init__(self):
        self._bundles: dict[str, OntologyBundle] = {}

    def get(self, namespace: str) -> OntologyBundle:
        if namespace not in self._bundles:
            self._bundles[namespace] = _build_bundle(namespace)

        return self._bundles[namespace]

    def evict(self, namespace: str) -> None:
        self._bundles.pop(namespace, None)


registry = OntologyRegistry()


# ----------------------------------------------------------------------
# Read API
# ----------------------------------------------------------------------


def node_label(bundle: OntologyBundle, node_id: str) -> str | None:
    if not bundle.graph.has_node(node_id):
        return None

    return bundle.graph.nodes[node_id].get("label")


def node_property(bundle: OntologyBundle, node_id: str, field: str):
    props = ontology_store.get_node_properties(
        bundle.entity_conn, bundle.namespace, node_id
    )
    return props.get(field) if props else None


def node_properties(
    bundle: OntologyBundle, node_id: str, fields: list[str] | None = None
) -> dict:
    props = (
        ontology_store.get_node_properties(
            bundle.entity_conn, bundle.namespace, node_id
        )
        or {}
    )

    if fields is None:
        return props

    return {field: props.get(field) for field in fields}


def find_ancestors(
    bundle: OntologyBundle,
    node_id: str,
    predicate: str = "instance_of",
    max_hops: int = 2,
    fields_by_hop: dict[int, list[str]] | None = None,
) -> dict[int, list[dict]]:
    """
    Walk `predicate`-typed edges outward from node_id up to max_hops,
    returning {hop: [{"node_id": ..., **requested scalar fields}, ...]}.
    Replaces the legacy Dgraph-based extract_ancestor_chain() traversal -
    no query strings, just a networkx walk filtered to one predicate.
    """

    result: dict[int, list[dict]] = {}
    frontier = [node_id]

    for hop in range(1, max_hops + 1):
        next_frontier: list[str] = []
        hop_nodes: list[dict] = []

        for source in frontier:
            if not bundle.graph.has_node(source):
                continue

            for _, target, data in bundle.graph.out_edges(source, data=True):
                if data.get("predicate") != predicate:
                    continue

                next_frontier.append(target)
                entry = {"node_id": target}
                for field in (fields_by_hop or {}).get(hop, []):
                    entry[field] = node_property(bundle, target, field)
                hop_nodes.append(entry)

        if not hop_nodes:
            break

        result[hop] = hop_nodes
        frontier = next_frontier

    return result


def superclass_chain(bundle: OntologyBundle, node_id: str) -> list[str]:
    """Walk subclass_of edges to the root - subclass_of is a tree in this domain."""

    chain: list[str] = []
    current = node_id
    seen = {current}

    while bundle.graph.has_node(current):
        parent = None

        for _, target, data in bundle.graph.out_edges(current, data=True):
            if data.get("predicate") == "subclass_of":
                parent = target
                break

        if parent is None or parent in seen:
            break

        chain.append(parent)
        seen.add(parent)
        current = parent

    return chain


def nodes_by_label(bundle: OntologyBundle, label: str) -> list[dict]:
    return [
        {"node_id": node_id, **attrs}
        for node_id, attrs in bundle.graph.nodes(data=True)
        if attrs.get("label") == label
    ]


def nodes_with_edge(
    bundle: OntologyBundle,
    predicate: str,
    source_ids: list[str] | None = None,
) -> list[dict]:
    results = []

    for source, target, data in bundle.graph.edges(data=True):
        if data.get("predicate") != predicate:
            continue
        if source_ids is not None and source not in source_ids:
            continue

        results.append({"source": source, "target": target})

    return results


def source_of_edge(
    bundle: OntologyBundle, predicate: str, target_node_id: str
) -> str | None:
    if not bundle.graph.has_node(target_node_id):
        return None

    for source, _, data in bundle.graph.in_edges(target_node_id, data=True):
        if data.get("predicate") == predicate:
            return source

    return None


# ----------------------------------------------------------------------
# Write API - writes target the tenant partition by default (never
# universal, unless the caller explicitly opts in), matching "tenant
# overrides shared" semantics used on read.
# ----------------------------------------------------------------------


def upsert_node(
    bundle: OntologyBundle,
    node_id: str,
    label: str,
    surface_texts: list[str] | None = None,
    scalar_props: dict | None = None,
    universal: bool = False,
) -> None:
    target = bundle.universal if universal else bundle.tenant
    target.add_entity(node_id, label, surface_texts=surface_texts)

    if scalar_props:
        ontology_store.upsert_node_properties(
            bundle.entity_conn,
            UNIVERSAL_NAMESPACE if universal else bundle.namespace,
            node_id,
            **scalar_props,
        )

    bundle.refresh_graph()


def upsert_edge(
    bundle: OntologyBundle,
    source: str,
    predicate: str,
    target_node: str,
    universal: bool = False,
    **attributes,
) -> str:
    target = bundle.universal if universal else bundle.tenant
    fact_id = target.add_fact(source, target_node, predicate, **attributes)
    bundle.refresh_graph()
    return fact_id


def delete_scalar_values(bundle: OntologyBundle, node_id: str, field: str) -> None:
    ontology_store.upsert_node_properties(
        bundle.entity_conn, bundle.namespace, node_id, **{field: None}
    )


def save(bundle: OntologyBundle) -> None:
    bundle.tenant.save(bundle.entity_conn)

    if bundle.universal is not bundle.tenant:
        bundle.universal.save(bundle.entity_conn)

    bundle.refresh_graph()
    bundle.literal_maps = None  # invalidate cached literal-attribute maps


def nodes_with_scalar_set(bundle: OntologyBundle, field: str) -> list[str]:
    """node_ids that have a non-null value for the given scalar ontology
    property - replaces KGHandler.get_nodes_having_predicate() for scalar
    (non-edge) predicates."""

    return ontology_store.list_nodes_with_property(
        bundle.entity_conn, bundle.namespace, field
    )
