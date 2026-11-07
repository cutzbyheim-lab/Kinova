from sqlalchemy.orm import Session

from app.core.context import RequestContext
from app.models import AuditLog


def audit(db: Session, ctx: RequestContext, action: str, entity_type: str, entity_id: object, **data: object) -> None:
    db.add(AuditLog(
        org_id=ctx.org_id, user_id=ctx.user_id, action=action,
        entity_type=entity_type, entity_id=str(entity_id), data=data,
    ))
