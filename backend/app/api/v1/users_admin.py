"""Staff users, audit log viewer, and the contact/newsletter inboxes."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.security import hash_password
from app.db.session import get_db
from app.models import AuditLog, ContactMessage, NewsletterSubscriber, RefreshToken, Role, User, UserRole
from app.services import audit
from app.services.passwords import PasswordError, validate_password
from app.services.user_rules import SUPER, UserRuleError, check_create, check_update

router = APIRouter(prefix="/admin", tags=["users-admin"])
u_read, u_write = require_permission("users.read"), require_permission("users.write")


def _view(u: User) -> dict:
    return {"id": u.id, "email": u.email, "full_name": u.full_name, "is_active": u.is_active, "roles": sorted(r.name for r in u.roles),
            "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None}


def _roles(db: Session, names: list[str]) -> list[Role]:
    rows = list(db.scalars(select(Role).where(Role.name.in_(names))))
    if len(rows) != len(set(names)):
        raise HTTPException(422, "Unknown role")
    return rows


def _live(db: Session, uid: int) -> User:
    u = db.get(User, uid)
    if u is None or u.deleted_at is not None:
        raise HTTPException(404, "User not found")
    return u


@router.get("/users")
def list_users(db: Session = Depends(get_db), _: User = Depends(u_read)):
    return [_view(u) for u in db.scalars(select(User).where(User.deleted_at.is_(None)).order_by(User.full_name))]


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=150)
    password: str = Field(max_length=200)
    roles: list[str] = Field(min_length=1)


@router.post("/users", status_code=201)
def create_user(d: UserCreate, db: Session = Depends(get_db), actor: User = Depends(u_write)):
    try:
        check_create(actor_is_super=actor.is_super_admin, new_roles=set(d.roles))
        validate_password(d.password, d.email)
    except (UserRuleError, PasswordError) as e:
        raise HTTPException(422, str(e))
    u = User(email=d.email.lower(), full_name=d.full_name.strip(), password_hash=hash_password(d.password), roles=_roles(db, d.roles))
    db.add(u)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A user with this email already exists")
    audit.record(db, actor, "user.create", "users", u.id, {"roles": d.roles})
    db.commit()
    return _view(u)


class UserUpdate(BaseModel):
    full_name: str = Field(min_length=1, max_length=150)
    is_active: bool
    roles: list[str] = Field(min_length=1)


@router.put("/users/{uid}")
def update_user(uid: int, d: UserUpdate, db: Session = Depends(get_db), actor: User = Depends(u_write)):
    u = _live(db, uid)
    others = db.scalar(select(func.count()).select_from(User).join(UserRole, UserRole.user_id == User.id).join(Role, Role.id == UserRole.role_id)
                       .where(Role.name == SUPER, User.is_active.is_(True), User.deleted_at.is_(None), User.id != uid))
    try:
        check_update(actor_id=actor.id, actor_is_super=actor.is_super_admin, target_id=uid, target_roles={r.name for r in u.roles},
                     new_roles=set(d.roles), target_active=u.is_active, new_active=d.is_active, other_active_supers=others or 0)
    except UserRuleError as e:
        raise HTTPException(422, str(e))
    before = {"roles": sorted(r.name for r in u.roles), "active": u.is_active}
    u.full_name, u.is_active, u.roles = d.full_name.strip(), d.is_active, _roles(db, d.roles)
    if not d.is_active:  # deactivation ends existing sessions
        db.execute(update(RefreshToken).where(RefreshToken.user_id == uid, RefreshToken.revoked_at.is_(None)).values(revoked_at=datetime.now(timezone.utc)))
    audit.record(db, actor, "user.update", "users", uid, {"before": before, "after": {"roles": sorted(d.roles), "active": d.is_active}})
    db.commit()
    return _view(u)


class PasswordReset(BaseModel):
    password: str = Field(max_length=200)


@router.post("/users/{uid}/password", status_code=204)
def reset_password(uid: int, d: PasswordReset, db: Session = Depends(get_db), actor: User = Depends(u_write)):
    u = _live(db, uid)
    if u.is_super_admin and not actor.is_super_admin:
        raise HTTPException(403, "Only a Super Admin can change a Super Admin's password")
    try:
        validate_password(d.password, u.email)
    except PasswordError as e:
        raise HTTPException(422, str(e))
    u.password_hash = hash_password(d.password)
    db.execute(update(RefreshToken).where(RefreshToken.user_id == uid, RefreshToken.revoked_at.is_(None)).values(revoked_at=datetime.now(timezone.utc)))
    audit.record(db, actor, "user.password_reset", "users", uid)  # the password itself is never logged
    db.commit()


@router.get("/audit-logs")
def audit_logs(action: str | None = None, entity_type: str | None = None, page: int = 1, page_size: int = 50,
               db: Session = Depends(get_db), _: User = Depends(require_permission("audit.read"))):
    page_size = max(1, min(page_size, 100))
    stmt = select(AuditLog, User.full_name).outerjoin(User, User.id == AuditLog.user_id)
    if action:
        stmt = stmt.where(AuditLog.action.ilike(f"{action.strip()[:60]}%"))
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type[:100])
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.execute(stmt.order_by(AuditLog.id.desc()).offset((max(page, 1) - 1) * page_size).limit(page_size)).all()
    return {"total": total, "items": [{"id": a.id, "user": name, "action": a.action, "entity_type": a.entity_type, "entity_id": a.entity_id,
                                       "changes": a.changes, "ip": a.ip_address, "at": a.created_at.isoformat()} for a, name in rows]}


# ---- inboxes (contact form + newsletter) ----
cms_read, cms_write = require_permission("cms.read"), require_permission("cms.write")


@router.get("/contact-messages")
def contact_messages(unread: bool = False, page: int = 1, page_size: int = 25, db: Session = Depends(get_db), _: User = Depends(cms_read)):
    page_size = max(1, min(page_size, 100))
    stmt = select(ContactMessage)
    if unread:
        stmt = stmt.where(ContactMessage.is_read.is_(False))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(ContactMessage.id.desc()).offset((max(page, 1) - 1) * page_size).limit(page_size)).all()
    return {"total": total, "items": [{"id": m.id, "name": m.name, "email": m.email, "phone": m.phone, "message": m.message,
                                       "is_read": m.is_read, "at": m.created_at.isoformat() if m.created_at else None} for m in rows]}


class ReadIn(BaseModel):
    is_read: bool = True


@router.put("/contact-messages/{mid}")
def mark_message(mid: int, d: ReadIn, db: Session = Depends(get_db), _: User = Depends(cms_write)):
    m = db.get(ContactMessage, mid)
    if m is None:
        raise HTTPException(404, "Message not found")
    m.is_read = d.is_read
    db.commit()
    return {"id": m.id, "is_read": m.is_read}


@router.get("/newsletter")
def subscribers(db: Session = Depends(get_db), _: User = Depends(cms_read)):
    rows = db.scalars(select(NewsletterSubscriber).order_by(NewsletterSubscriber.id.desc()).limit(5000)).all()
    return [{"id": s.id, "email": s.email, "is_active": s.is_active, "at": s.created_at.isoformat() if s.created_at else None} for s in rows]
