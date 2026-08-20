import math
from dataclasses import dataclass, field

from talkingdb_pt.services.kg.store import (
    OntologyBundle,
    node_property,
    nodes_by_label,
    nodes_with_edge,
    nodes_with_scalar_set,
)

LITERAL_ATTRIBUTE_TYPE = "Class_Type_Literal_Attribute"
DIMENSION_CONJUNCTION_TYPE = "Instance_Type_Dimension_Conjunction"
DIMENSIONS_ELEMENT = "dimensions"
LENGTH_ELEMENT = "length"


@dataclass
class LiteralMaps:
    # element_name -> {"literals": {lit_id: {"pt_prec": num, "default_unit": unit_id|None}}}
    ele_lit_map: dict = field(default_factory=dict)
    # unit_id -> {"elements": [element names this unit is used by], "aliases": [unit_id, *surface_texts]}
    unit_ele_map: dict = field(default_factory=dict)
    # element_name -> {lit_id: {...}} - the dimensions element's literals, re-keyed by
    # the element each literal's default unit actually belongs to
    ele_dim_map: dict = field(default_factory=dict)
    # lit_id -> {"range": (min, max), "pt_prec": num}
    lit_range_map: dict = field(default_factory=dict)
    # shorthand (lowercased) -> {"value": shorthand, "multiplier": num|None, "symbol_for": node_id}
    symbol_map: dict = field(default_factory=dict)
    # conjunction words used to split compound dimensional values ("2x2", "2 by 3")
    dim_conj: list = field(default_factory=list)


def _node_surface_texts(bundle: OntologyBundle, node_id: str) -> list[str]:
    if not bundle.graph.has_node(node_id):
        return []
    return list(bundle.graph.nodes[node_id].get("surface_texts", []))


def _edge_sources(bundle: OntologyBundle, predicate: str, target: str) -> list[str]:
    return [
        edge["source"]
        for edge in nodes_with_edge(bundle, predicate)
        if edge["target"] == target
    ]


def _edge_target(bundle: OntologyBundle, predicate: str, source: str) -> str | None:
    for edge in nodes_with_edge(bundle, predicate):
        if edge["source"] == source:
            return edge["target"]
    return None


def _build_ele_lit_map(bundle: OntologyBundle) -> dict:
    ele_lit_map = {}

    for element_node in nodes_by_label(bundle, LITERAL_ATTRIBUTE_TYPE):
        element_name = element_node["node_id"]
        literals = {}

        for lit_id in _edge_sources(bundle, "instance_of", element_name):
            literals[lit_id] = {
                "pt_prec": node_property(bundle, lit_id, "pt_prec") or math.inf,
                "default_unit": _edge_target(bundle, "default_unit", lit_id),
            }

        ele_lit_map[element_name] = {"literals": literals}

    return ele_lit_map


def _build_unit_ele_map(bundle: OntologyBundle) -> dict:
    unit_ele_map = {}
    unit_ids = {edge["target"] for edge in nodes_with_edge(bundle, "has_units")}

    for unit_id in unit_ids:
        elements = _edge_sources(bundle, "has_units", unit_id)
        unit_ele_map[unit_id] = {
            "elements": elements,
            "aliases": [unit_id, *_node_surface_texts(bundle, unit_id)],
        }

    return unit_ele_map


def _build_ele_dim_map(ele_lit_map: dict, unit_ele_map: dict) -> dict:
    ele_dim_map: dict = {}
    dim_literals = ele_lit_map.get(DIMENSIONS_ELEMENT, {}).get("literals", {})

    for lit_id, lit_info in dim_literals.items():
        default_unit = lit_info["default_unit"]
        if not default_unit:
            continue

        elements = unit_ele_map.get(default_unit, {}).get("elements", [])
        if not elements:
            continue

        element = elements[0]
        ele_dim_map.setdefault(element, {})[lit_id] = lit_info

    return ele_dim_map


def _build_lit_range_map(bundle: OntologyBundle) -> dict:
    lit_range_map = {}
    literal_ids = {edge["source"] for edge in nodes_with_edge(bundle, "default_unit")}

    for lit_id in literal_ids:
        range_min = node_property(bundle, lit_id, "range_min")
        range_max = node_property(bundle, lit_id, "range_max")
        bounds = sorted(
            v for v in (range_min, range_max) if v is not None
        ) or [-1, -1]

        lit_range_map[lit_id] = {
            "range": tuple(bounds),
            "pt_prec": node_property(bundle, lit_id, "pt_prec") or math.inf,
        }

    return lit_range_map


def _build_symbol_map(bundle: OntologyBundle) -> dict:
    symbol_map = {}

    for node_id in nodes_with_scalar_set(bundle, "shorthands"):
        shorthands = node_property(bundle, node_id, "shorthands") or []
        multiplier = node_property(bundle, node_id, "multiplier")

        for shorthand in shorthands:
            key = shorthand.lower()
            if key not in symbol_map:
                symbol_map[key] = {
                    "value": key,
                    "multiplier": multiplier,
                    "symbol_for": node_id,
                }

    return symbol_map


def _build_dim_conj(bundle: OntologyBundle) -> list:
    nodes = nodes_by_label(bundle, DIMENSION_CONJUNCTION_TYPE)
    if not nodes:
        return []

    node_id = nodes[0]["node_id"]
    return [node_id, *_node_surface_texts(bundle, node_id)]


def build_literal_maps(bundle: OntologyBundle) -> LiteralMaps:
    ele_lit_map = _build_ele_lit_map(bundle)
    unit_ele_map = _build_unit_ele_map(bundle)

    return LiteralMaps(
        ele_lit_map=ele_lit_map,
        unit_ele_map=unit_ele_map,
        ele_dim_map=_build_ele_dim_map(ele_lit_map, unit_ele_map),
        lit_range_map=_build_lit_range_map(bundle),
        symbol_map=_build_symbol_map(bundle),
        dim_conj=_build_dim_conj(bundle),
    )


def get_literal_maps(bundle: OntologyBundle) -> LiteralMaps:
    """Cached on the bundle, invalidated by kg.store.save()."""

    if bundle.literal_maps is None:
        bundle.literal_maps = build_literal_maps(bundle)

    return bundle.literal_maps
