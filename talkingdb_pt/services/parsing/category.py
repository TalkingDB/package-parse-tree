from talkingdb_pt.services.kg.store import (
    OntologyBundle,
    find_ancestors,
    node_property,
    superclass_chain,
)


def _is_resolvable(bundle: OntologyBundle, entity_id: str) -> bool:
    """An NER match only participates in category resolution if it
    resolves to a real ontology node. Replaces the legacy hardcoded
    `kg_id != "number_patterns"` check - any regex match that isn't a
    registered ontology entity (e.g. a bare numeric-literal pattern) is
    excluded the same way, without a magic string."""

    return bundle.graph.has_node(entity_id)


def extract_ctg_entities(bundle: OntologyBundle, ner_output: dict) -> tuple[list, list]:
    """Split NER matches into pure category mentions and category-instance
    mentions, based on the `contains` scalar property."""

    categories = []
    ctg_instances = []

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

        if node_property(bundle, entity_id, "contains") == "instances":
            categories.append(record)
            continue

        parents = find_ancestors(
            bundle, entity_id, "instance_of", max_hops=1, fields_by_hop={1: ["contains"]}
        ).get(1, [])

        if any(p.get("contains") == "instances" for p in parents):
            ctg_instances.append(record)

    return categories, ctg_instances


def deduce_category_from_ins(bundle: OntologyBundle, ctg_instances: list) -> None:
    """For each category-instance, record the category ids it directly
    belongs to (its instance_of parents that themselves contain instances)."""

    for instance in ctg_instances:
        entity_id = instance["metadata"]["entity_id"]
        parents = find_ancestors(
            bundle, entity_id, "instance_of", max_hops=1, fields_by_hop={1: ["contains"]}
        ).get(1, [])

        instance["metadata"]["categories"] = {
            "kg": [p["node_id"] for p in parents if p.get("contains") == "instances"],
            "exact_men": {},
        }


def associate_category_to_ins(
    bundle: OntologyBundle, ctg_instances: list, categories: list, ner_output: dict
) -> None:
    """If the query explicitly names both an instance and one of its valid
    categories nearby (e.g. "smartphone iphone 15"), prefer that explicit
    mention over other candidate categories. Sliding-window search
    left/right from the instance's position, matching the legacy
    associate_category_to_ins - scanning across every NER match in the
    sentence (not just categories/instances), so distances match legacy."""

    ner_indices = sorted({tuple(v["location"]) for v in ner_output.values()})
    indices_map = {tuple(v["location"]): v for v in ner_output.values()}
    by_loc = {tuple(c["loc"]): c for c in categories + ctg_instances}

    def find_nearby_category(instance: dict) -> dict:
        loc = tuple(instance["loc"])
        valid_categories = instance["metadata"]["categories"]["kg"]
        anchor = ner_indices.index(loc)
        candidates = {}

        # Two independent scans (right then left) starting at the instance's
        # own position. Each stops at the first category-like node found in
        # that direction, recording it only if it's a valid category for
        # this instance - matching the legacy sliding-window semantics
        # exactly (skip unresolvable entries silently, break on the first
        # real category regardless of validity, don't skip anything else).
        for step in (1, -1):
            cursor = anchor
            while 0 <= cursor < len(ner_indices):
                candidate_loc = ner_indices[cursor]
                candidate_entity_id = indices_map[candidate_loc]["entity_id"]

                if _is_resolvable(bundle, candidate_entity_id):
                    if node_property(bundle, candidate_entity_id, "contains") == "instances":
                        if candidate_entity_id in valid_categories:
                            candidates[candidate_loc] = {
                                **by_loc[candidate_loc],
                                "dist": cursor - anchor,
                            }
                        break

                cursor += step

        if not candidates:
            return {}

        best_loc = min(candidates, key=lambda k: abs(candidates[k]["dist"]))
        return candidates[best_loc]

    for instance in ctg_instances:
        if len(instance["metadata"]["categories"]["kg"]) <= 1:
            continue

        match = find_nearby_category(instance)
        if match:
            instance["metadata"]["categories"]["exact_men"] = match


def add_classes_to_ctg(bundle: OntologyBundle, ner_output: dict) -> list[dict]:
    """Build the category filter table for a parsed query: one row per
    resolved (instance, category) pair, plus one row per bare category
    mention with no specific instance."""

    categories, ctg_instances = extract_ctg_entities(bundle, ner_output)
    deduce_category_from_ins(bundle, ctg_instances)
    associate_category_to_ins(bundle, ctg_instances, categories, ner_output)

    ctg_table = []
    categories_considered = set()

    for instance in ctg_instances:
        meta = instance["metadata"]
        row = {
            "instance": meta["entity_id"],
            "instance_id": meta["entity_id"],
            "instance_loc": instance["loc"],
            "instance_surface_text": instance["surface_text"],
        }

        candidates = meta["categories"]["kg"]
        category_id = None

        if len(candidates) == 1:
            category_id = candidates[0]
        elif len(candidates) > 1:
            exact_men = meta["categories"]["exact_men"]
            if exact_men:
                category_id = exact_men["metadata"]["entity_id"]
                row["loc"] = exact_men["loc"]
                row["surface_text"] = exact_men["surface_text"]
            else:
                common_ancestors: set = set()
                for candidate_id in candidates:
                    chain = {candidate_id, *superclass_chain(bundle, candidate_id)}
                    common_ancestors = (
                        chain if not common_ancestors else common_ancestors & chain
                    )
                if common_ancestors:
                    category_id = next(iter(common_ancestors))

        if category_id:
            row["category"] = category_id
            row["category_id"] = category_id  # node_id == src_id, no uid lookup needed
            categories_considered.add(category_id)
            ctg_table.append(row)

    for category in categories:
        entity_id = category["metadata"]["entity_id"]
        if entity_id in categories_considered:
            continue

        ctg_table.append(
            {
                "instance": "*",
                "category": entity_id,
                "category_id": entity_id,
                "category_src_name": node_property(bundle, entity_id, "src_name"),
                "loc": category["loc"],
                "surface_text": category["surface_text"],
            }
        )
        categories_considered.add(entity_id)

    return ctg_table


def category_query_similarity(category_name: str, query: str, m: int, n: int) -> int:
    """Longest common substring length between a category name and a query,
    used to rank category matches by textual similarity. Pure algorithm,
    ported as-is."""

    category_name = " ".join(category_name.split("-"))
    lcs = [[0] * (n + 1) for _ in range(m + 1)]
    result = 0

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if category_name[i - 1] == query[j - 1]:
                lcs[i][j] = lcs[i - 1][j - 1] + 1
                result = max(result, lcs[i][j])

    return result
