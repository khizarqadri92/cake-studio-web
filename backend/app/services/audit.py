from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import AuditLog, User


def record(db: Session, actor: User, action: str, entity_type: str, entity_id=None, changes: dict | None = None) -> None:
    db.add(
        AuditLog(
            user_id=actor.id,
            action=action,
            entity_type=entity_type,
            entity_id=None if entity_id is None else str(entity_id),
            changes=changes,
            created_at=datetime.now(timezone.utc),
        )
    )
