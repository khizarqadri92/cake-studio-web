from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_account, rate_limit
from app.core.config import get_settings
from app.core.security import create_access_token, hash_password, hash_refresh_token, new_refresh_token, verify_password
from app.db.session import get_db
from app.models import AccountToken, CustomerAccount, RefreshToken
from app.services import notify, shop
from app.services.passwords import PasswordError, hash_token, new_token, token_usable, validate_password

router = APIRouter(prefix="/auth/customer", tags=["customer-auth"])
# A valid hash to verify against when the e-mail is unknown, so response time does not reveal which e-mails exist.
_DUMMY_HASH = hash_password("not-a-real-password-for-timing")


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=200)
    full_name: str = Field(min_length=1, max_length=150)
    phone: str | None = Field(None, max_length=32)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=200)


class RefreshIn(BaseModel):
    refresh_token: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


def _issue(db: Session, a: CustomerAccount) -> TokenOut:
    raw, hashed = new_refresh_token()
    now = datetime.now(timezone.utc)
    db.add(RefreshToken(account_id=a.id, token_hash=hashed, created_at=now, expires_at=now + timedelta(days=get_settings().refresh_token_days)))
    db.commit()
    return TokenOut(access_token=create_access_token(str(a.id), principal="customer"), refresh_token=raw)


def _send_token(db: Session, a: CustomerAccount, kind: str) -> None:
    raw, hashed = new_token()
    now = datetime.now(timezone.utc)
    db.add(AccountToken(account_id=a.id, kind=kind, token_hash=hashed, expires_at=now + timedelta(hours=24 if kind == "verify" else 1)))
    site = shop.get_group(db, "general")["site_name"]
    path = "verify-email" if kind == "verify" else "reset-password"
    link = f"{get_settings().public_base_url.rstrip('/')}/account/{path}?token={raw}"
    if kind == "verify":
        subject, body = f"{site}: confirm your email", f"Hi {a.full_name.split()[0]},\n\nPlease confirm your email address:\n{link}\n\nThe link is valid for 24 hours."
    else:
        subject, body = f"{site}: reset your password", f"Hi {a.full_name.split()[0]},\n\nReset your password here:\n{link}\n\nThe link is valid for 1 hour. If you didn't ask for this, ignore this email."
    notify.enqueue_account_email(db, a.email, subject, body, link)


@router.post("/register", status_code=202, dependencies=[Depends(rate_limit("register", 5, 60))])
def register(d: RegisterIn, db: Session = Depends(get_db)):
    email = d.email.lower()
    try:
        validate_password(d.password, email)
        phone = shop.normalize_phone(d.phone) if d.phone else None
    except (PasswordError, shop.CheckoutError) as e:
        raise HTTPException(422, getattr(e, "message", None) or str(e))
    existing = db.scalar(select(CustomerAccount).where(CustomerAccount.email == email))
    if existing is None:
        a = CustomerAccount(email=email, password_hash=hash_password(d.password), full_name=d.full_name.strip(), phone=phone)
        db.add(a)
        try:
            db.flush()
        except IntegrityError:  # lost a race with a concurrent registration for the same e-mail
            db.rollback()
            return {"ok": True}
        _send_token(db, a, "verify")
        db.commit()
    # Same response whether or not the e-mail was already registered: no account enumeration.
    return {"ok": True}


@router.post("/login", response_model=TokenOut, dependencies=[Depends(rate_limit("clogin", 10, 60))])
def login(d: LoginIn, db: Session = Depends(get_db)):
    a = db.scalar(select(CustomerAccount).where(CustomerAccount.email == d.email.lower(), CustomerAccount.deleted_at.is_(None)))
    ok = verify_password(d.password, a.password_hash if a else _DUMMY_HASH)
    if a is None or not ok or not a.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    a.last_login_at = datetime.now(timezone.utc)
    return _issue(db, a)


@router.post("/refresh", response_model=TokenOut, dependencies=[Depends(rate_limit("crefresh", 30, 60))])
def refresh(d: RefreshIn, db: Session = Depends(get_db)):
    t = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(d.refresh_token)))
    now = datetime.now(timezone.utc)
    if not t or t.account_id is None or t.revoked_at is not None or t.expires_at < now:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")
    a = db.get(CustomerAccount, t.account_id)
    if a is None or not a.is_active or a.deleted_at is not None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")
    t.revoked_at = now  # single use: rotated on every refresh
    return _issue(db, a)


@router.post("/logout", status_code=204)
def logout(d: RefreshIn, db: Session = Depends(get_db)):
    t = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(d.refresh_token), RefreshToken.account_id.is_not(None)))
    if t and t.revoked_at is None:
        t.revoked_at = datetime.now(timezone.utc)
        db.commit()


class TokenIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)


def _consume(db: Session, raw: str, kind: str) -> CustomerAccount:
    t = db.scalar(select(AccountToken).where(AccountToken.token_hash == hash_token(raw), AccountToken.kind == kind).with_for_update())
    now = datetime.now(timezone.utc)
    if t is None or not token_usable(t.expires_at, t.used_at, now):
        raise HTTPException(422, "This link is invalid or has expired")
    t.used_at = now  # single use
    return db.get(CustomerAccount, t.account_id)


@router.post("/verify-email", dependencies=[Depends(rate_limit("cverify", 10, 60))])
def verify_email(d: TokenIn, db: Session = Depends(get_db)):
    a = _consume(db, d.token, "verify")
    a.email_verified_at = a.email_verified_at or datetime.now(timezone.utc)
    db.commit()
    return {"ok": True}


@router.post("/resend-verification", status_code=202, dependencies=[Depends(rate_limit("cresend", 3, 300))])
def resend(a: CustomerAccount = Depends(get_current_account), db: Session = Depends(get_db)):
    if a.email_verified_at is None:
        _send_token(db, a, "verify")
        db.commit()
    return {"ok": True}


class ForgotIn(BaseModel):
    email: EmailStr


@router.post("/password/forgot", status_code=202, dependencies=[Depends(rate_limit("cforgot", 5, 300))])
def forgot(d: ForgotIn, db: Session = Depends(get_db)):
    a = db.scalar(select(CustomerAccount).where(CustomerAccount.email == d.email.lower(), CustomerAccount.deleted_at.is_(None), CustomerAccount.is_active.is_(True)))
    if a:
        _send_token(db, a, "reset")
        db.commit()
    return {"ok": True}  # identical response for unknown e-mails


class ResetIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    password: str = Field(max_length=200)


@router.post("/password/reset", dependencies=[Depends(rate_limit("creset", 10, 60))])
def reset(d: ResetIn, db: Session = Depends(get_db)):
    a = _consume(db, d.token, "reset")
    try:
        validate_password(d.password, a.email)
    except PasswordError as e:
        db.rollback()  # keep the link usable so the customer can retry with a better password
        raise HTTPException(422, str(e))
    a.password_hash = hash_password(d.password)
    a.email_verified_at = a.email_verified_at or datetime.now(timezone.utc)  # they proved control of the mailbox
    db.execute(update(RefreshToken).where(RefreshToken.account_id == a.id, RefreshToken.revoked_at.is_(None)).values(revoked_at=datetime.now(timezone.utc)))
    db.commit()  # all existing sessions are signed out
    return {"ok": True}
