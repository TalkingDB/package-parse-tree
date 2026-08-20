import sqlite3

from talkingdb.clients.sqlite import ENTITY_DB, sqlite_conn
from talkingdb.models.entity.entity import EntityModel

from talkingdb_pt.services.ontology.store import init_db as init_ontology_db

entity_conn = sqlite_conn(ENTITY_DB).__enter__()
entity_conn.row_factory = sqlite3.Row

EntityModel.init_db(entity_conn)
init_ontology_db(entity_conn)
