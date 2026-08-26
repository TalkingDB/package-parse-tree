from dataclasses import dataclass, field

from talkingdb_pt.services.kg.store import (
    OntologyBundle,
    find_ancestors,
    nodes_with_edge,
    source_of_edge,
)
from talkingdb_pt.services.parsing.literal_maps import LiteralMaps, get_literal_maps
from talkingdb_pt.services.parsing.utils import attr_sort_order, return_num

NUMBER_PATTERN_MARKER = "number_patterns"
LENGTH_ELEMENT_FALLBACK = "length"


@dataclass
class LiteralContext:
    """Pipeline state threaded through extraction/association, mirroring
    the legacy LiteralUnitsHandler's instance attributes."""

    ner_output: dict
    maps: LiteralMaps
    num_comps: list = field(default_factory=list)
    comparators: list = field(default_factory=list)
    units: list = field(default_factory=list)
    exact_lit: list = field(default_factory=list)
    ner_indices: list = field(default_factory=list)
    ner_indices_map: dict = field(default_factory=dict)


def _parents(bundle: OntologyBundle, entity_id: str) -> set:
    if not bundle.graph.has_node(entity_id):
        return set()

    parents = find_ancestors(bundle, entity_id, "instance_of", max_hops=1).get(1, [])
    return {p["node_id"] for p in parents}


def _has_default_unit(bundle: OntologyBundle, entity_id: str) -> bool:
    return bundle.graph.has_node(entity_id) and any(
        edge["source"] == entity_id for edge in nodes_with_edge(bundle, "default_unit")
    )


def handle_dimensions(maps: LiteralMaps, output: dict, num_st: str) -> bool:
    """Compound dimensional values ("2x2x1 cm", "3 by 4"). Returns True and
    fills `output` if num_st contains a registered dimension conjunction."""

    conj = next((c for c in maps.dim_conj if num_st.find(c) != -1), None)
    if conj is None:
        return False

    output["value_type"] = "dimensions"
    parts = num_st.split(conj)
    dim_values = [handle_numerical_surface_texts(maps, p) for p in parts]

    output["value"] = "x".join(str(d["value"]) for d in dim_values)

    symbols = [d["symbol"] for d in dim_values]
    if any(symbols):
        output["symbol"] = next(s for s in symbols if s is not None)
    else:
        first_part = parts[0]
        for unit_id, unit_info in maps.unit_ele_map.items():
            if any(first_part.find(alias) != -1 for alias in unit_info["aliases"]):
                output["symbol"] = unit_id
                break

    return True


def handle_numerical_surface_texts(maps: LiteralMaps, num_st: str) -> dict:
    output = {"value": None, "symbol": None, "value_type": None}

    if handle_dimensions(maps, output, num_st):
        return output

    num, num_type = return_num(num_st) or [None, None]
    output["value"] = num
    output["value_type"] = num_type

    for symbol, info in maps.symbol_map.items():
        if symbol not in num_st:
            continue

        if info["multiplier"]:
            output["value"] = num * info["multiplier"]
            output["value_type"] = "int"
            output["symbol"] = info["symbol_for"]
        else:
            output["symbol"] = info["symbol_for"]
        break

    return output


def extract_literal_entities(bundle: OntologyBundle, ctx: LiteralContext) -> None:
    ctx.exact_lit = [
        {
            "entity_id": key,
            "surface_text": v["surface_text"],
            "loc": v["location"],
            "metadata": {"entity_id": v["entity_id"]},
        }
        for key, v in ctx.ner_output.items()
        if _has_default_unit(bundle, v["entity_id"])
    ]
    ctx.units = [
        {
            "entity_id": key,
            "surface_text": v["surface_text"],
            "loc": v["location"],
            "metadata": {"entity_id": v["entity_id"]},
        }
        for key, v in ctx.ner_output.items()
        if "unit" in _parents(bundle, v["entity_id"])
    ]
    ctx.comparators = [
        {
            "entity_id": key,
            "surface_text": v["surface_text"],
            "loc": v["location"],
            "metadata": {"entity_id": v["entity_id"]},
        }
        for key, v in ctx.ner_output.items()
        if "comparator" in _parents(bundle, v["entity_id"])
    ]
    ctx.num_comps = [
        {
            "entity_id": key,
            "surface_text": v["surface_text"],
            "loc": v["location"],
            "metadata": {},
        }
        for key, v in ctx.ner_output.items()
        if NUMBER_PATTERN_MARKER in key
    ]
    # Legacy embeds this call inside extract_literal_entities (num_comps is
    # literally the return value of associate_comps_to_nums there) - kept
    # in the same place here rather than as a separate later pipeline step.
    associate_comps_to_nums(bundle, ctx)


def _scan_direction(
    ctx: LiteralContext,
    anchor: int,
    step: int,
    stop_condition,
    skip_number_patterns: bool = True,
) -> dict:
    """One directional sliding-window pass from `anchor`, moving by `step`.
    `stop_condition(det)` returns: None to keep sliding past this entry,
    False to stop here without recording anything, or a dict to record and
    stop. Returns {loc: {**result, "dist": ...}} or {} if nothing recorded
    before running off the end of the list.

    `skip_number_patterns` matches the legacy behavior split: the
    unit/literal/category association scans never treat a bare number as a
    candidate (they're looking for KG-linked entities), so they silently
    slide past number_patterns entries without invoking stop_condition on
    them at all. associate_comps_to_nums is the opposite - it's searching
    FOR a number - so it must pass skip_number_patterns=False."""

    cursor = anchor
    while 0 <= cursor < len(ctx.ner_indices):
        loc = ctx.ner_indices[cursor]
        det = ctx.ner_indices_map[loc]

        if not skip_number_patterns or NUMBER_PATTERN_MARKER not in det["key"]:
            result = stop_condition(det)
            if result is not None:
                if result:
                    return {loc: {**result, "dist": cursor - anchor}}
                return {}

        cursor += step

    return {}


def _best(*candidate_maps: dict) -> dict:
    merged = {}
    for m in candidate_maps:
        merged.update(m)

    if not merged:
        return {}

    best_loc = min(merged, key=lambda k: abs(merged[k]["dist"]))
    return {best_loc: merged[best_loc]}


def associate_comps_to_nums(bundle: OntologyBundle, ctx: LiteralContext) -> None:
    """Comparators only look to the right for a number ("above 1000",
    never "1000 above") - matches the legacy map_comps_to_num, which never
    scans left at all."""

    for comp in ctx.comparators:
        anchor = ctx.ner_indices.index(tuple(comp["loc"]))

        def stop(det):
            if NUMBER_PATTERN_MARKER in det["key"]:
                return {
                    "surface_text": det["surface_text"],
                    "entity_id": det["entity_id"],
                }
            return None  # comparators keep sliding past non-number entities

        match = _scan_direction(ctx, anchor, 1, stop, skip_number_patterns=False)
        if not match:
            continue

        loc = next(iter(match))
        target = next((n for n in ctx.num_comps if tuple(n["loc"]) == loc), None)
        if target is not None:
            target["metadata"]["comparator"] = {
                "surface_text": comp["surface_text"],
                "loc": comp["loc"],
                "entity_id": comp["metadata"]["entity_id"],
                "dist": match[loc]["dist"],
            }


def deduce_literal_from_num(bundle: OntologyBundle, ctx: LiteralContext) -> None:
    for num in ctx.num_comps:
        values = handle_numerical_surface_texts(ctx.maps, num["surface_text"])
        num["metadata"]["values"] = values
        num["metadata"]["literal"] = {"kg": {}, "exact_lit": {}}

        symbol = values["symbol"]
        value_type = values["value_type"]

        if symbol and symbol in ctx.maps.unit_ele_map:
            elements = ctx.maps.unit_ele_map[symbol]["elements"]
            element = elements[0] if elements else None
            if value_type == "dimensions":
                num["metadata"]["literal"]["kg"] = ctx.maps.ele_dim_map.get(element, {})
            elif element:
                num["metadata"]["literal"]["kg"] = ctx.maps.ele_lit_map.get(
                    element, {}
                ).get("literals", {})
        else:
            value = values["value"]
            if value_type == "dimensions":
                num["metadata"]["literal"]["kg"] = ctx.maps.ele_dim_map.get(
                    LENGTH_ELEMENT_FALLBACK, {}
                )
            elif value_type in ("int", "float") and value is not None:
                in_range = {
                    lit_id: info
                    for lit_id, info in ctx.maps.lit_range_map.items()
                    if len(info["range"]) >= 2
                    and info["range"][0] <= value <= info["range"][1]
                }
                if in_range:
                    num["metadata"]["literal"]["kg"] = in_range


def deduce_literal_from_unit(ctx: LiteralContext) -> None:
    for unit in ctx.units:
        unit["metadata"]["literal"] = {"kg": {}, "exact_lit": {}}
        elements = ctx.maps.unit_ele_map.get(unit["metadata"]["entity_id"], {}).get(
            "elements", []
        )

        merged = {}
        for element in elements:
            merged.update(ctx.maps.ele_lit_map.get(element, {}).get("literals", {}))
        unit["metadata"]["literal"]["kg"] = merged


def associate_lits_or_units_to_num(bundle: OntologyBundle, ctx: LiteralContext) -> None:
    """For each number, find the nearest unit or exact-literal mention.
    Asymmetric scan (matches legacy map_exact_lit_or_units_to_num exactly):
    if a unit is found while scanning right, the left scan is skipped
    entirely - a unit mention always wins over a more-distant literal
    mention found only by looking left."""

    deduce_literal_from_num(bundle, ctx)

    for num in ctx.num_comps:
        num["metadata"]["unit"] = {}
        anchor = ctx.ner_indices.index(tuple(num["loc"]))

        def stop(det, num=num):
            if "unit" in _parents(bundle, det["entity_id"]):
                return {
                    "surface_text": det["surface_text"],
                    "entity_id": det["entity_id"],
                    "unit_mapped": True,
                }
            if _has_default_unit(bundle, det["entity_id"]):
                if det["entity_id"] in num["metadata"]["literal"]["kg"]:
                    return {
                        "surface_text": det["surface_text"],
                        "entity_id": det["entity_id"],
                        "unit_mapped": False,
                    }
                return False
            return None

        right = _scan_direction(ctx, anchor, 1, stop)
        if right and next(iter(right.values()))["unit_mapped"]:
            match = right
        else:
            left = _scan_direction(ctx, anchor, -1, stop)
            match = _best(right, left)

        if not match:
            continue

        loc = next(iter(match))
        entry = match[loc]

        if entry["unit_mapped"]:
            found = next((u for u in ctx.units if tuple(u["loc"]) == loc), None)
            if found is not None:
                num["metadata"]["unit"] = found
        else:
            found = next((e for e in ctx.exact_lit if tuple(e["loc"]) == loc), None)
            if found is not None:
                num["metadata"]["literal"]["exact_lit"] = found


def associate_literals_to_units(bundle: OntologyBundle, ctx: LiteralContext) -> None:
    deduce_literal_from_unit(ctx)

    for unit in ctx.units:
        anchor = ctx.ner_indices.index(tuple(unit["loc"]))

        def stop(det, unit=unit):
            if _has_default_unit(bundle, det["entity_id"]):
                if det["entity_id"] in unit["metadata"]["literal"]["kg"]:
                    return {
                        "surface_text": det["surface_text"],
                        "entity_id": det["entity_id"],
                    }
                return False
            return None

        right = _scan_direction(ctx, anchor, 1, stop)
        left = _scan_direction(ctx, anchor, -1, stop)
        match = _best(right, left)
        if not match:
            continue

        loc = next(iter(match))
        found = next((e for e in ctx.exact_lit if tuple(e["loc"]) == loc), None)
        if found is not None:
            unit["metadata"]["literal"]["exact_lit"] = found


def add_literals_to_aft(bundle: OntologyBundle, ner_output: dict) -> list[dict]:
    maps = get_literal_maps(bundle)
    ctx = LiteralContext(ner_output=ner_output, maps=maps)

    ctx.ner_indices = sorted(tuple(v["location"]) for v in ner_output.values())
    ctx.ner_indices_map = {
        tuple(v["location"]): {"key": k, **v} for k, v in ner_output.items()
    }

    extract_literal_entities(bundle, ctx)  # also associates comparators to nums
    associate_literals_to_units(bundle, ctx)
    associate_lits_or_units_to_num(bundle, ctx)

    aft = []

    for num in ctx.num_comps:
        meta = num["metadata"]
        if "values" not in meta:
            continue

        row: dict = {"comparator": {}}
        if "comparator" in meta:
            row["comparator"] = {
                "name": meta["comparator"]["entity_id"],
                "surface_text": meta["comparator"]["surface_text"],
                "loc": meta["comparator"]["loc"],
            }
        else:
            row["comparator"]["name"] = "eq"
        row["sort_order"] = attr_sort_order(row["comparator"])

        value = meta["values"]["value"]
        row["attr_value_kg_id"] = value
        row["attr_value"] = value
        row["attr_value_surface_text"] = num["surface_text"]
        row["attr_value_loc"] = num["loc"]

        kg = meta["literal"]["kg"]
        attr_name = None

        if len(kg) == 1:
            attr_name = next(iter(kg))
        elif len(kg) > 1:
            unit = meta.get("unit") or {}
            if unit:
                row["unit"] = {
                    "surface_text": unit["surface_text"],
                    "loc": unit["loc"],
                    "name": unit["metadata"]["entity_id"],
                    "uri": unit["metadata"]["entity_id"],
                }
                exact_lit = unit["metadata"]["literal"].get("exact_lit")
                if exact_lit:
                    attr_name = exact_lit["metadata"]["entity_id"]
                    row["attr_name_surface_text"] = exact_lit.get("surface_text")
                    row["attr_name_loc"] = exact_lit.get("loc")
                else:
                    attr_name = min(kg, key=lambda k: kg[k]["pt_prec"])
            else:
                exact_lit = meta["literal"].get("exact_lit")
                if exact_lit:
                    attr_name = exact_lit["metadata"]["entity_id"]
                else:
                    attr_name = min(kg, key=lambda k: kg[k]["pt_prec"])

        if attr_name:
            row["attr_name"] = attr_name
            row["attr_name_kg_id"] = source_of_edge(bundle, "has_attributes", attr_name)
            aft.append(row)

    return aft
