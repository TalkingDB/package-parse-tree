import pytest
from fastapi import HTTPException
from talkingdb.models.auth.api_key import APIKeyModel

from talkingdb_pt.services.auth import auth_conn, get_api_key


@pytest.mark.anyio
async def test_get_api_key_accepts_valid_key():
    created = APIKeyModel.create(auth_conn, "someone@example.com")

    user_email = await get_api_key(api_key_header=created.api_key)

    assert user_email == "someone@example.com"


@pytest.mark.anyio
async def test_get_api_key_rejects_unknown_key():
    with pytest.raises(HTTPException) as exc_info:
        await get_api_key(api_key_header="not-a-real-key")

    assert exc_info.value.status_code == 403


@pytest.mark.anyio
async def test_get_api_key_rejects_missing_key():
    with pytest.raises(HTTPException) as exc_info:
        await get_api_key(api_key_header=None)

    assert exc_info.value.status_code == 403
