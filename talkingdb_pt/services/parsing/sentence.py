from talkingdb_pt.model.nl import (
    ExtractGroups,
    NLAttribute,
    NLAttributeComparator,
    NLAttributeUnit,
    NLAttributeValue,
    NLCategory,
    NLInstance,
)
from talkingdb_pt.services.kg.store import OntologyBundle
from talkingdb_pt.services.ner.client import build_ner_ids, extract_and_link
from talkingdb_pt.services.parsing.attrs_unifier import filter_attributes
from talkingdb_pt.services.parsing.category import (
    add_classes_to_ctg,
    category_query_similarity,
)
from talkingdb_pt.services.parsing.literal import add_literals_to_aft
from talkingdb_pt.services.parsing.object_attrs import add_object_attrs_to_aft
from talkingdb_pt.services.parsing.stopwords import filter_stop_words


def assign_attrs(
    attrs_filter_table: list[dict], target_attributes: list[NLAttribute]
) -> None:
    """Fold attribute-filter-table rows into an instance's or category's
    `attributes` list, grouping multiple values under one NLAttribute per
    distinct attr_name (mutates target_attributes in place)."""

    by_name = {a.name: a for a in target_attributes}

    for row in attrs_filter_table:
        attr = by_name.get(row["attr_name"])
        if attr is None:
            attr = NLAttribute(
                name=row["attr_name"],
                uri=row.get("attr_name_kg_id"),
                surface_text=row.get("attr_name_surface_text"),
                loc=row.get("attr_name_loc"),
            )
            target_attributes.append(attr)
            by_name[row["attr_name"]] = attr

        comparator = row.get("comparator") or {}
        attr.values.append(
            NLAttributeValue(
                name=row["attr_value"],
                uri=row.get("attr_value_kg_id"),
                surface_text=row.get("attr_value_surface_text"),
                loc=row.get("attr_value_loc"),
                comparator=NLAttributeComparator(
                    name=comparator.get("name"),
                    surface_text=comparator.get("surface_text"),
                    loc=comparator.get("loc"),
                ),
                sort_order=row.get("sort_order"),
            )
        )

        if "unit" in row:
            attr.unit = NLAttributeUnit(**row["unit"])


async def parse_input(bundle: OntologyBundle, text: str) -> dict:
    text = text.lower()

    nel_response = await extract_and_link(bundle.namespace, text)
    ner_output = build_ner_ids(nel_response)
    no_tag_entities = nel_response.get("no_tag_entities", [])

    ctg_table = add_classes_to_ctg(bundle, ner_output)

    attrs_filter_table = [
        *add_object_attrs_to_aft(bundle, ner_output),
        *add_literals_to_aft(bundle, ner_output),
    ]

    groups: dict[str, NLCategory] = {}
    extract_groups = ExtractGroups(groups=[])

    if ctg_table:
        instance_rows = [row for row in ctg_table if row["instance"] != "*"]
        for row in instance_rows:
            category = groups.get(row["category"])
            if category is None:
                category = NLCategory(
                    name=row["category"],
                    uri=row["category_id"],
                    src_name=row.get("category_src_name"),
                    surface_text=row.get("surface_text"),
                    loc=row.get("loc"),
                )
                groups[row["category"]] = category

            instance = NLInstance(
                name=row["instance"],
                uri=row["instance_id"],
                surface_text=row.get("instance_surface_text"),
                loc=row.get("instance_loc"),
            )
            assign_attrs(attrs_filter_table, instance.attributes)
            category.instances.append(instance)

        bare_category_rows = [row for row in ctg_table if row["instance"] == "*"]
        for row in bare_category_rows:
            category = groups.get(row["category"])
            if category is None:
                category = NLCategory(
                    name=row["category"],
                    uri=row["category_id"],
                    src_name=row.get("category_src_name"),
                    surface_text=row.get("surface_text"),
                    loc=row.get("loc"),
                )
                groups[row["category"]] = category

            assign_attrs(attrs_filter_table, category.attributes)
            category.attributes = filter_attributes(
                bundle, row["category_id"], category.attributes
            )
            category.score = category_query_similarity(
                category.name, text, len(category.name), len(text)
            )

        extract_groups.groups = sorted(
            groups.values(), key=lambda c: c.score, reverse=True
        )
    else:
        misc_category = NLCategory()
        assign_attrs(attrs_filter_table, misc_category.attributes)
        if misc_category.attributes:
            extract_groups.groups.append(misc_category)

    no_tag_surface_texts = filter_stop_words(
        [e["surface_text"] for e in no_tag_entities]
    )
    search_weight = len(nel_response.get("universal_entities", []))

    return {
        "parse_tree_output": extract_groups,
        "no_tag_entities": no_tag_entities,
        "search_weight": search_weight,
        "entities_extracted": nel_response,
        "total_tokens": search_weight + len(no_tag_surface_texts),
    }
