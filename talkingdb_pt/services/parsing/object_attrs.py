from talkingdb_pt.services.kg.store import (
    OntologyBundle,
    find_ancestors,
    node_property,
    source_of_edge,
)
from talkingdb_pt.services.parsing.category import _is_resolvable
from talkingdb_pt.services.parsing.utils import attr_sort_order


def extract_obj_attr_entities(
    bundle: OntologyBundle, ner_output: dict
) -> tuple[list, list]:
    """Split NER matches into attribute-class mentions (e.g. "color") and
    attribute-value mentions (e.g. "red"), based on the `contains` scalar
    property - mirrors category.extract_ctg_entities but for "attributes"
    instead of "instances"."""

    attr_classes = []
    attr_values = []

    for key, entry in ner_output.items():
        entity_id = entry["entity_id"]
        if not _is_resolvable(bundle, entity_id):
            continue

        record = {
            "entity_id": key,
            "surface_text": entry["surface_text"],
            "loc": entry["location"],
            "metadata": {"entity_id": entity_id},
        }

        if node_property(bundle, entity_id, "contains") == "attributes":
            attr_classes.append(record)
            continue

        parents = find_ancestors(
            bundle,
            entity_id,
            "instance_of",
            max_hops=1,
            fields_by_hop={1: ["contains"]},
        ).get(1, [])

        if any(p.get("contains") == "attributes" for p in parents):
            attr_values.append(record)

    return attr_classes, attr_values


def deduce_attr_class_from_attr_value(
    bundle: OntologyBundle, attr_values: list
) -> None:
    """For each attribute-value mention, record the attribute-class ids it
    directly belongs to (its instance_of parents that themselves contain
    attributes)."""

    for value in attr_values:
        entity_id = value["metadata"]["entity_id"]
        parents = find_ancestors(
            bundle,
            entity_id,
            "instance_of",
            max_hops=1,
            fields_by_hop={1: ["contains"]},
        ).get(1, [])

        value["metadata"]["attr_classes"] = {
            "kg": [p["node_id"] for p in parents if p.get("contains") == "attributes"],
            # Legacy's exact-mention sliding window for attribute classes
            # (associate_attr_class_to_attr_ins) was already fully disabled
            # (commented out) in the source - not ported, kept empty here
            # to match that existing behavior exactly.
            "exact_men": {},
        }


def add_object_attrs_to_aft(bundle: OntologyBundle, ner_output: dict) -> list[dict]:
    """Build the attribute filter table: one row per resolved
    (attribute-class, value) pair extracted from the query."""

    _, attr_values = extract_obj_attr_entities(bundle, ner_output)
    deduce_attr_class_from_attr_value(bundle, attr_values)

    aft = []

    for value in attr_values:
        meta = value["metadata"]
        candidates = meta["attr_classes"]["kg"]

        if len(candidates) == 1:
            attr_names = candidates
        elif len(candidates) > 1:
            exact_men = meta["attr_classes"].get("exact_men")
            attr_names = (
                [exact_men["metadata"]["entity_id"]] if exact_men else candidates
            )
        else:
            attr_names = []

        for attr_name in attr_names:
            comparator = {"name": "uid_in"}
            aft.append(
                {
                    "attr_name": attr_name,
                    "comparator": comparator,
                    "sort_order": attr_sort_order(comparator),
                    "attr_value": meta["entity_id"],
                    "attr_value_kg_id": meta["entity_id"],
                    "attr_value_surface_text": value["surface_text"],
                    "attr_value_loc": value["loc"],
                    "attr_name_kg_id": source_of_edge(
                        bundle, "has_attributes", attr_name
                    ),
                }
            )

    return aft
