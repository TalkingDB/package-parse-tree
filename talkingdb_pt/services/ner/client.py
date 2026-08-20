import os

import httpx

NEL_SERVER = os.environ.get("NEL_SERVER", "http://localhost:8092")


async def extract_and_link(
    namespace: str, text: str, word_correction: bool = False
) -> dict:
    """Call package-named-entity-linker's extraction API directly.

    Replaces the legacy NERCaller, which called through the now-retired
    `cm` (conversation moderation) proxy service at NL_SERVER/newMessage.
    cm was a thin fan-out with no logic worth preserving (confirmed by
    audit) - this calls NEL directly instead.
    """

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{NEL_SERVER}/api/namespaces/{namespace}/extractions",
            json={"message_text": text, "word_correction": word_correction},
        )
        response.raise_for_status()
        return response.json()


def filter_overlapping_regex(
    universal_entities: list[dict], regex_entities: list[dict]
) -> list[dict]:
    """Drop regex matches whose start falls inside a universal-entity span.

    Direct port of the legacy RegexHandler.filter_rgx - pure span-overlap
    filtering, unrelated to any database.
    """

    universal_spans = [tuple(e["index"]) for e in universal_entities]
    overlapping = {
        tuple(rgx["index"])
        for rgx in regex_entities
        for uni_start, uni_end in universal_spans
        if uni_start <= rgx["index"][0] < uni_end
    }

    return [e for e in regex_entities if tuple(e["index"]) not in overlapping]


def build_ner_ids(extraction_response: dict) -> dict:
    """Reshape NEL's extraction response into the entity-resolution map
    consumed by category/object-attribute resolution.

    Simplification vs. the legacy ner_ids: NEL entity_ids are already plain
    strings (no Dgraph uid/src_id duality), so there is no
    kg_id###kg_name_id composite to parse apart - one `entity_id` field
    serves both roles the legacy code split into kg_id/kg_name_id.

    Keyed by f"{entity_id}&&{start}&&{end}" (one entry per linked entity
    per span - a span can resolve to more than one entity).
    """

    universal_entities = extraction_response.get("universal_entities", [])
    regex_entities = extraction_response.get("regex_entities", [])
    filtered_regex = filter_overlapping_regex(universal_entities, regex_entities)

    ner_ids: dict = {}

    for span in universal_entities:
        start, end = span["index"]
        for entity in span.get("entities", []):
            key = f"{entity['entity_id']}&&{start}&&{end}"
            ner_ids[key] = {
                "location": [start, end],
                "surface_text": span["surface_text"],
                "entity_id": entity["entity_id"],
            }

    for span in filtered_regex:
        start, end = span["index"]
        key = f"{span['rule']}&&{start}&&{end}"
        ner_ids[key] = {
            "location": [start, end],
            "surface_text": span["surface_text"],
            "entity_id": span["rule"],
        }

    return ner_ids
