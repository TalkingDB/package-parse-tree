# Troubleshooting

[Docs home](README.md) › Troubleshooting

| Symptom | Likely cause | Fix |
| :--- | :--- | :--- |
| `httpx.ConnectError` or a 5xx from `/extract/*` or `/ner/train` | NEL is not running at `NEL_SERVER` (default `http://localhost:8092`) | Start [package-named-entity-linker](https://github.com/TalkingDB/package-named-entity-linker) or set `NEL_SERVER` |
| NEL returns `404 Namespace not found` through parse-tree | The namespace exists in parse-tree but not in NEL | Create it in NEL with `POST /api/namespaces` |
| A new node's name is never recognised | NEL was not trained after the node was written | Call `POST /api/namespaces/{ns}/ner/train` |
| `/ner/train` reports `entities_skipped` above 0 | One upsert failed (for example a NEL conflict or timeout); training continues past it | Check NEL's logs for those node IDs and train again |
| `400` when writing [ontology](https://en.wikipedia.org/wiki/Ontology_(information_science)) data | The node's `class_type` or `instance_type` was never registered, or it uses a reserved key wrongly | Register the type first; see reserved keys in [architecture.md](architecture.md#how-the-ontology-is-stored) |
| A relationship you wrote has no effect on filters | Only `instance_of`, `subclass_of`, `has_attributes`, `has_units` and `default_unit` are followed as edges | Store the value as a scalar property, or extend the allowlist in `services/kg/query.py` |
| A query finds the category but ignores "red" or "stainless" | Attribute values do not narrow the graph filter yet | Known limitation; filter on returned attributes in the caller for now |
| Numbers parse with the wrong unit | The attribute has no default unit, or the unit word is not a trained [surface text](https://github.com/TalkingDB/ConceptDigger/blob/main/docs/concepts.md#surface-texts-every-name-for-a-thing) | Add the unit's names as surface texts and set `default_unit` |
| `ModuleNotFoundError: No module named 'talkingdb'` | `base-tdb-*` not installed or not on the path | `make sync MODE=git && poetry install`, or `MODE=local` for side by side work |
| The API accepts requests without any key | The API key check in `services/auth.py` is not attached to routes | Expected today. Do not expose the service publicly without a gateway |

---

**Related:** [Architecture](architecture.md) · [Usage and examples](usage-and-examples.md) · [README](../README.md)
