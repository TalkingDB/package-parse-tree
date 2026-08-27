# package-parse-tree

An ontology-driven natural-language query parser. Given a type/instance/attribute
ontology (of any domain), it parses free-text queries into structured
knowledge-graph queries: resolving categories and instances, disambiguating by
graph proximity, and extracting typed attribute filters (including numeric
values with units and comparators).

This package is domain-agnostic TalkingDB infrastructure: it has no built-in
concept of "products," "ecommerce," or any other specific domain. Domain-specific
vocabulary and use cases (for example, ecommerce product search) are owned by
the `module-*` repos that consume this package, not by the package itself.

## Status

All 6 build milestones are implemented and tested (129 service/API tests, plus
a `PTClient` dual-mode client with its own test coverage). See
`talkingdb_pt/services/kg/store.py` for the ontology/knowledge-graph store
(built on `base-tdb-models`' `EntityModel`, no external graph database
required).

## Client

`talkingdb_pt.client.PTClient` gives callers a single interface that works two
ways, controlled by the `CLIENT_MODE` env var (defaults to `direct`):

- **DIRECT mode**: calls the same service functions the API routers call,
  in-process. No server needed, useful when this package is embedded as a
  library inside another service (e.g. a future `module-ecommerce-ai`).
- **API mode**: calls a deployed package-parse-tree service over HTTP. Set
  `CLIENT_MODE=api` and `PT_HOST` to the deployed base URL.

```python
from talkingdb_pt.client import PTClient

client = PTClient()  # direct mode by default
result = await client.extract_relations("acme", "red running shoes under $50")
```

## Development

```
make sync MODE=git      # or MODE=local for editable base-tdb-* checkouts
poetry install
make test
make local               # run with hot reload
```

See `Makefile` for the full list of targets.
