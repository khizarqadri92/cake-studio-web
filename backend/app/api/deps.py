import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import decode_access_token
from app.services.ratelimit import limiter
from app.db.session import get_db
from app.models import CustomerAccount, User

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        payload = decode_access_token(creds.credentials)
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    if payload.get("principal") != "staff":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Staff access only")
    user = db.scalar(select(User).where(User.id == int(payload["sub"]), User.deleted_at.is_(None)))
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User inactive or missing")
    return user


def require_permission(code: str):
    """Dependency factory: Super Admin bypasses; others need the permission code."""

    def checker(user: User = Depends(get_current_user)) -> User:
        if user.is_super_admin or code in user.permission_codes:
            return user
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"Missing permission: {code}")

    return checker


def client_ip(request: Request) -> str:
    if get_settings().trust_proxy_headers:  # only behind a proxy that overwrites the header
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[-1].strip()  # last hop = the address our own proxy saw
    return request.client.host if request.client else "unknown"


def rate_limit(name: str, limit: int, window_s: int):
    def dep(request: Request) -> None:
        if not limiter.allow(f"{name}:{client_ip(request)}", limit, window_s):
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many requests, please try again shortly")

    return dep


def _account_from_token(creds, db: Session) -> CustomerAccount | None:
    if creds is None:
        return None
    try:
        payload = decode_access_token(creds.credentials)
    except jwt.PyJWTError:
        return None
    if payload.get("principal") != "customer":
        return None
    a = db.scalar(select(CustomerAccount).where(CustomerAccount.id == int(payload["sub"]), CustomerAccount.deleted_at.is_(None)))
    return a if a is not None and a.is_active else None


def get_current_account(creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> CustomerAccount:
    a = _account_from_token(creds, db)
    if a is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Please log in")
    return a


def optional_account(creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> CustomerAccount | None:
    """For guest-or-logged-in endpoints such as checkout: a bad/absent token simply means 'guest'."""
    return _account_from_token(creds, db)
