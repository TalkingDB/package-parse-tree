import os
import sqlite3

from fastapi import HTTPException, Security
from fastapi.security.api_key import APIKeyHeader
from starlette.status import HTTP_403_FORBIDDEN
from talkingdb.clients.sqlite import sqlite_conn
from talkingdb.models.auth.api_key import APIKeyModel

AUTH_DB = os.environ.get("AUTH_DB", "data/auth.db")
API_KEY_NAME = "SEARCH-API-KEY"

auth_conn = sqlite_conn(AUTH_DB).__enter__()
auth_conn.row_factory = sqlite3.Row
APIKeyModel.init_db(auth_conn)

api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


async def get_api_key(api_key_header: str = Security(api_key_header)) -> str:
    """Not currently attached to any router (matches the legacy service's
    own state - defined but never wired to a Depends()). Left ready for
    whichever future milestone decides to actually enforce it; forcing
    that now would be an unannounced breaking change to existing callers.
    """

    user_email = APIKeyModel.verify(auth_conn, api_key_header)
    if user_email is None:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN, detail="Please provide a valid API Key"
        )
    return user_email
