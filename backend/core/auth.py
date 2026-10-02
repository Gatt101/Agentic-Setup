from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from core.config import settings


@dataclass(frozen=True)
class AuthenticatedActor:
    user_id: str
    role: str
    display_name: str = "Clinician"


_bearer = HTTPBearer(auto_error=False)


def _unauthorized(detail: str = "Invalid or expired session token.") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def decode_clerk_token(token: str) -> AuthenticatedActor:
    if not settings.clerk_jwt_key.strip() or not settings.clerk_issuer.strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Clerk backend verification is not configured.",
        )

    try:
        header = jwt.get_unverified_header(token)
        if header.get("alg") != "RS256":
            raise _unauthorized("Unsupported session-token algorithm.")

        claims: dict[str, Any] = jwt.decode(
            token,
            settings.clerk_jwt_key.replace("\\n", "\n"),
            algorithms=["RS256"],
            issuer=settings.clerk_issuer.rstrip("/"),
            options={"verify_aud": False, "require_exp": True, "require_sub": True},
        )
    except HTTPException:
        raise
    except JWTError as exc:
        raise _unauthorized() from exc

    authorized_party = str(claims.get("azp") or "").rstrip("/")
    allowed_parties = settings.clerk_authorized_party_list
    if authorized_party and authorized_party not in allowed_parties:
        raise _unauthorized("Session token was issued for an unauthorized application.")

    if claims.get("sts") == "pending":
        raise _unauthorized("Account setup is incomplete.")

    user_id = str(claims.get("sub") or "").strip()
    role = str(claims.get("role") or "").strip().lower()
    if not user_id:
        raise _unauthorized("Session token has no user identity.")
    if role not in {"doctor", "patient"}:
        raise _unauthorized("Account role has not been provisioned.")

    display_name = str(
        claims.get("full_name") or claims.get("name") or "Clinician"
    ).strip()
    return AuthenticatedActor(
        user_id=user_id,
        role=role,
        display_name=display_name or "Clinician",
    )


async def get_current_actor(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> AuthenticatedActor:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized("Authentication required.")
    return decode_clerk_token(credentials.credentials)


async def require_doctor(
    actor: AuthenticatedActor = Depends(get_current_actor),
) -> AuthenticatedActor:
    if actor.role != "doctor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Doctor access required.",
        )
    return actor
