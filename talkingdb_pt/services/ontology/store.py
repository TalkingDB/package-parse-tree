import json
import sqlite3
from datetime import datetime, timezone

UNIVERSAL_NAMESPACE = "universal"


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS ontology_types (
            namespace TEXT NOT NULL,
            kg_type_name TEXT NOT NULL,
            type_name TEXT NOT NULL,
            is_class INTEGER NOT NULL,
            is_instance INTEGER NOT NULL,
            class_type_group TEXT,
            instance_type_group TEXT,
            extra_attrs_json TEXT NOT NULL,
            relationship_triples_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (namespace, kg_type_name)
        );

        CREATE INDEX IF NOT EXISTS idx_ontology_types_lookup
        ON ontology_types(namespace, class_type_group, instance_type_group);

        CREATE TABLE IF NOT EXISTS ontology_node_properties (
            namespace TEXT NOT NULL,
            node_id TEXT NOT NULL,
            src_name TEXT,
            contains TEXT,
            pt_prec INTEGER,
            range_min REAL,
            range_max REAL,
            multiplier REAL,
            shorthands TEXT,
            src_url TEXT,
            is_a TEXT,
            extra_json TEXT,
            PRIMARY KEY (namespace, node_id)
        );

        CREATE INDEX IF NOT EXISTS idx_ontology_node_properties_contains
        ON ontology_node_properties(namespace, contains);
        """
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ----------------------------------------------------------------------
# ontology_types
# ----------------------------------------------------------------------


def upsert_ontology_type(
    conn: sqlite3.Connection,
    namespace: str,
    kg_type_name: str,
    type_name: str,
    is_class: bool,
    is_instance: bool,
    class_type_group: str | None = None,
    instance_type_group: str | None = None,
    extra_attrs: dict | None = None,
    relationship_triples: list | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO ontology_types(
            namespace, kg_type_name, type_name, is_class, is_instance,
            class_type_group, instance_type_group,
            extra_attrs_json, relationship_triples_json, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(namespace, kg_type_name) DO UPDATE SET
            type_name = excluded.type_name,
            is_class = excluded.is_class,
            is_instance = excluded.is_instance,
            class_type_group = excluded.class_type_group,
            instance_type_group = excluded.instance_type_group,
            extra_attrs_json = excluded.extra_attrs_json,
            relationship_triples_json = excluded.relationship_triples_json
        """,
        (
            namespace,
            kg_type_name,
            type_name,
            int(is_class),
            int(is_instance),
            class_type_group,
            instance_type_group,
            json.dumps(extra_attrs or {}),
            json.dumps(relationship_triples or []),
            _now(),
        ),
    )
    conn.commit()


def _row_to_ontology_type(row: sqlite3.Row) -> dict:
    return {
        "namespace": row["namespace"],
        "kg_type_name": row["kg_type_name"],
        "type_name": row["type_name"],
        "is_class": bool(row["is_class"]),
        "is_instance": bool(row["is_instance"]),
        "class_type_group": row["class_type_group"],
        "instance_type_group": row["instance_type_group"],
        "extra_attrs": json.loads(row["extra_attrs_json"]),
        "relationship_triples": json.loads(row["relationship_triples_json"]),
        "created_at": row["created_at"],
    }


def get_ontology_type(
    conn: sqlite3.Connection,
    namespace: str,
    kg_type_name: str,
) -> dict | None:
    row = conn.execute(
        "SELECT * FROM ontology_types WHERE namespace = ? AND kg_type_name = ?",
        (namespace, kg_type_name),
    ).fetchone()

    return _row_to_ontology_type(row) if row else None


def find_ontology_type(
    conn: sqlite3.Connection,
    namespace: str,
    group: str,
    data_type: str,
    type_name: str | None = None,
) -> dict | None:
    """
    Search namespace first, then fall back to the universal namespace -
    the tenant-overlay lookup order the legacy KGAnatomyHandler.get_kg_type
    implemented against two Mongo collections. `data_type` is either
    "class_type_group" or "instance_type_group"; if more than one match is
    found within a namespace, disambiguate by `type_name`.
    """

    if data_type not in ("class_type_group", "instance_type_group"):
        raise ValueError(f"invalid data_type: {data_type}")

    for ns in (namespace, UNIVERSAL_NAMESPACE):
        rows = conn.execute(
            f"SELECT * FROM ontology_types WHERE namespace = ? AND {data_type} = ?",  # noqa: S608
            (ns, group),
        ).fetchall()

        if not rows:
            continue

        if len(rows) == 1:
            return _row_to_ontology_type(rows[0])

        if type_name is not None:
            for row in rows:
                if row["type_name"] == type_name:
                    return _row_to_ontology_type(row)

        return _row_to_ontology_type(rows[0])

    return None


def list_ontology_types(conn: sqlite3.Connection, namespace: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM ontology_types WHERE namespace IN (?, ?) ORDER BY kg_type_name",
        (namespace, UNIVERSAL_NAMESPACE),
    ).fetchall()

    return [_row_to_ontology_type(row) for row in rows]


# ----------------------------------------------------------------------
# ontology_node_properties
# ----------------------------------------------------------------------

_PROPERTY_COLUMNS = (
    "src_name",
    "contains",
    "pt_prec",
    "range_min",
    "range_max",
    "multiplier",
    "shorthands",
    "src_url",
    "is_a",
    "extra_json",
)


def upsert_node_properties(
    conn: sqlite3.Connection,
    namespace: str,
    node_id: str,
    **properties,
) -> None:
    unknown = set(properties) - set(_PROPERTY_COLUMNS)
    if unknown:
        raise ValueError(f"unknown node properties: {sorted(unknown)}")

    if "shorthands" in properties and not isinstance(
        properties["shorthands"], str
    ):
        properties["shorthands"] = json.dumps(properties["shorthands"])

    if "extra_json" in properties and not isinstance(
        properties["extra_json"], str
    ):
        properties["extra_json"] = json.dumps(properties["extra_json"])

    existing = get_node_properties(conn, namespace, node_id, fallback=False) or {}
    merged = {**existing, **properties}

    columns = ["namespace", "node_id", *_PROPERTY_COLUMNS]
    values = [namespace, node_id, *(merged.get(col) for col in _PROPERTY_COLUMNS)]
    placeholders = ", ".join("?" for _ in columns)
    update_clause = ", ".join(
        f"{col} = excluded.{col}" for col in _PROPERTY_COLUMNS
    )

    conn.execute(
        f"""
        INSERT INTO ontology_node_properties({", ".join(columns)})
        VALUES ({placeholders})
        ON CONFLICT(namespace, node_id) DO UPDATE SET {update_clause}
        """,  # noqa: S608
        values,
    )
    conn.commit()


def get_node_properties(
    conn: sqlite3.Connection,
    namespace: str,
    node_id: str,
    fallback: bool = True,
) -> dict | None:
    """
    Tenant-overlay lookup: a namespace-scoped row wins if present; falls
    back to the universal-scoped row for the same node_id when `fallback`
    is True (the read path). Writes (`fallback=False`) must only see the
    exact (namespace, node_id) row so they merge onto the right partition.
    """

    namespaces = (namespace,) if not fallback else (namespace, UNIVERSAL_NAMESPACE)

    for ns in namespaces:
        row = conn.execute(
            "SELECT * FROM ontology_node_properties WHERE namespace = ? AND node_id = ?",
            (ns, node_id),
        ).fetchone()

        if row:
            result = {col: row[col] for col in _PROPERTY_COLUMNS}
            if result.get("shorthands"):
                result["shorthands"] = json.loads(result["shorthands"])
            if result.get("extra_json"):
                result["extra_json"] = json.loads(result["extra_json"])
            return result

    return None


def list_nodes_with_property(
    conn: sqlite3.Connection, namespace: str, field: str
) -> list[str]:
    """node_ids (universal + namespace) that have a non-null value set for
    the given scalar property column. Replaces the legacy
    KGHandler.get_nodes_having_predicate() for scalar (non-edge)
    predicates like "shorthands"."""

    if field not in _PROPERTY_COLUMNS:
        raise ValueError(f"unknown node property: {field}")

    rows = conn.execute(
        f"SELECT DISTINCT node_id FROM ontology_node_properties "  # noqa: S608
        f"WHERE namespace IN (?, ?) AND {field} IS NOT NULL",
        (namespace, UNIVERSAL_NAMESPACE),
    ).fetchall()

    return [row["node_id"] for row in rows]
