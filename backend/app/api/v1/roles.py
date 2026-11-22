from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models import AuditLog, Permission, Role, User

router = APIRouter(prefix="/admin/roles", tags=["roles"])


class RoleOut(BaseModel):
    id: int
    name: str
    is_system: bool
    permissions: list[str]


class SetPermissionsIn(BaseModel):
    permissions: list[str]


def _out(r: Role) -> RoleOut:
    return RoleOut(id=r.id, name=r.name, is_system=r.is_system, permissions=sorted(p.code for p in r.permissions))


@router.get("", response_model=list[RoleOut])
def list_roles(db: Session = Depends(get_db), _: User = Depends(require_permission("roles.read"))):
    return [_out(r) for r in db.scalars(select(Role).order_by(Role.id))]


@router.get("/permissions", response_model=list[str])
def list_permissions(db: Session = Depends(get_db), _: User = Depends(require_permission("roles.read"))):
    return [p.code for p in db.scalars(select(Permission).order_by(Permission.code))]


@router.put("/{role_id}/permissions", response_model=RoleOut)
def set_permissions(
    role_id: int,
    data: SetPermissionsIn,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("roles.write")),
):
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(404, "Role not found")
    if role.name == "Super Admin":
        raise HTTPException(400, "Super Admin permissions are not editable")
    perms = list(db.scalars(select(Permission).where(Permission.code.in_(data.permissions))))
    if len(perms) != len(set(data.permissions)):
        raise HTTPException(422, "Unknown permission code supplied")
    before = sorted(p.code for p in role.permissions)
    role.permissions = perms
    db.add(
        AuditLog(
            user_id=actor.id,
            action="role.permissions.update",
            entity_type="role",
            entity_id=str(role.id),
            changes={"before": before, "after": sorted(data.permissions)},
            created_at=datetime.now(timezone.utc),
        )
    )
    db.commit()
    db.refresh(role)
    return _out(role)
