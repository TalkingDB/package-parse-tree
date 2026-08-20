from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from talkingdb_pt import __version__
from talkingdb_pt.api import ontology

OPENAPI_TAGS = [
    {
        "name": "Ontology",
        "description": "Registering ontology types and writing ontology data.",
    },
    {
        "name": "Extraction",
        "description": "Parsing free-text queries against an ontology into "
        "structured graph queries.",
    },
    {
        "name": "Knowledge Graph",
        "description": "Querying ontology data directly.",
    },
]

app = FastAPI(
    title="TalkingDB Parse Tree",
    description=(
        "Ontology-driven natural-language query parser: given a "
        "type/instance/attribute ontology, parses free-text queries into "
        "structured knowledge-graph queries."
    ),
    version=__version__,
    openapi_tags=OPENAPI_TAGS,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ontology.router)
