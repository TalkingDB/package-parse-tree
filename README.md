# package-parse-tree

An ontology-driven natural-language query parser. Given a type/instance/attribute
ontology (of any domain), it parses free-text queries into structured
knowledge-graph queries — resolving categories and instances, disambiguating by
graph proximity, and extracting typed attribute filters (including numeric
values with units and comparators).

This package is domain-agnostic TalkingDB infrastructure: it has no built-in
concept of "products," "ecommerce," or any other specific domain. Domain-specific
vocabulary and use cases (for example, ecommerce product search) are owned by
the `module-*` repos that consume this package, not by the package itself.

## Status

Under active development — see `talkingdb_pt/services/kg/store.py` for the
current ontology/knowledge-graph store (built on `base-tdb-models`' `EntityModel`,
no external graph database required).

## Development

```
make sync MODE=git      # or MODE=local for editable base-tdb-* checkouts
poetry install
make test
make local               # run with hot reload
```

See `Makefile` for the full list of targets.
