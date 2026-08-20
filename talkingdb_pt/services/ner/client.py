import os

import httpx

NEL_SERVER = os.environ.get("NEL_SERVER", "http://localhost:8092")


class NELEntityConflict(Exception):
    """The entity already exists (NEL returned 409)."""


class NELEntityNotFound(Exception):
    """The entity does not exist (NEL returned 404)."""


async def get_entity(namespace: str, entity_id: str) -> dict | None:
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{NEL_SERVER}/api/namespaces/{namespace}/entities/{entity_id}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()


async def create_entity(
    namespace: str, entity_id: str, label: str, surface_texts: list[str]
) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{NEL_SERVER}/api/namespaces/{namespace}/entities",
            json={"entity_id": entity_id, "label": label, "surface_texts": surface_texts},
        )
        if response.status_code == 409:
            raise NELEntityConflict(entity_id)
        response.raise_for_status()
        return response.json()


async def update_entity_surface_texts(
    namespace: str, entity_id: str, surface_texts: list[str]
) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.patch(
            f"{NEL_SERVER}/api/namespaces/{namespace}/entities/{entity_id}",
            json={"surface_texts": surface_texts},
        )
        if response.status_code == 404:
            raise NELEntityNotFound(entity_id)
        response.raise_for_status()
        return response.json()


async def add_entity_surface_text(namespace: str, entity_id: str, surface_text: str) -> dict | None:
    """Returns None (no-op) if the surface text is already registered -
    NEL has no dedicated "remove one surface text" endpoint, only this
    additive one plus a full-replace PATCH, so callers that need removal
    read the current entity and PATCH the reduced list instead."""

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{NEL_SERVER}/api/namespaces/{namespace}/entities/{entity_id}/surface-texts",
            json={"surface_text": surface_text},
        )
        if response.status_code == 409:
            return None
        if response.status_code == 404:
            raise NELEntityNotFound(entity_id)
        response.raise_for_status()
        return response.json()


async def upsert_entity(
    namespace: str, entity_id: str, label: str, surface_texts: list[str]
) -> dict:
    """Create the entity, or update its surface texts if it already exists."""

    try:
        return await create_entity(namespace, entity_id, label, surface_texts)
    except NELEntityConflict:
        return await update_entity_surface_texts(namespace, entity_id, surface_texts)


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
