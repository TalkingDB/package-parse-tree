from fastapi import APIRouter
from pydantic import BaseModel, Field

from talkingdb_pt.services.ner.client import extract_and_link

router = APIRouter(
    prefix="/api/namespaces/{namespace}/extract",
    tags=["Extraction"],
)


class ExtractEntitiesRequest(BaseModel):
    user_query: str = Field(..., description="Free text to extract entities from.")
    word_correction: bool = Field(
        False, description="Enable fuzzy typo correction when matching entities."
    )


@router.post("/entities")
async def extract_entities(namespace: str, request: ExtractEntitiesRequest) -> dict:
    """Thin passthrough to the NER/NEL extraction result - matches the
    legacy /extract/entities endpoint, which returned raw NER output
    without further processing. Category/attribute resolution happens in
    /extract/relations (a later milestone), not here."""

    return await extract_and_link(
        namespace, request.user_query, request.word_correction
    )
