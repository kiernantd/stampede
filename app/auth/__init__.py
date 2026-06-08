import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_bearer = HTTPBearer()


async def get_current_user_id(
    _credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> uuid.UUID:
    # Phase 2: real Cognito JWT verification goes here.
    # Tests override this via app.dependency_overrides[get_current_user_id].
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="auth_not_implemented",
    )
