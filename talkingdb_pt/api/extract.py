from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from talkingdb_pt.api.dependencies import get_ontology_bundle
from talkingdb_pt.model.nl import NLOutput
from talkingdb_pt.services.kg.store import OntologyBundle
from talkingdb_pt.services.ner.client import extract_and_link
from talkingdb_pt.services.parsing.sentence import parse_input

router = APIRouter(
    prefix="/api/namespaces/{namespace}/extract",
    tags=["Extraction"],
)


class ExtractEntitiesRequest(BaseModel):
    user_query: str = Field(..., description="Free text to extract entities from.")
    word_correction: bool = Field(
        False, description="Enable fuzzy typo correction when matching entities."
    )


class ExtractRelationsRequest(BaseModel):
    user_query: str = Field(..., description="Free text to parse against the ontology.")


@router.post("/entities")
async def extract_entities(namespace: str, request: ExtractEntitiesRequest) -> dict:
    """Thin passthrough to the NER/NEL extraction result - matches the
    legacy /extract/entities endpoint, which returned raw NER output
    without further processing. Category/attribute resolution happens in
    /extract/relations, not here."""

    return await extract_and_link(
        namespace, request.user_query, request.word_correction
    )


@router.post("/relations", response_model=NLOutput)
async def extract_relations(
    namespace: str,
    request: ExtractRelationsRequest,
    bundle: OntologyBundle = Depends(get_ontology_bundle),
) -> dict:
    """Parses a free-text query against this namespace's ontology into
    structured category/instance/attribute groups - the full ontology-
    driven query-parsing pipeline (NER -> category resolution -> attribute
    resolution -> grouping)."""

    return await parse_input(bundle, request.user_query)
