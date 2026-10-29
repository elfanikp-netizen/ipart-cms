from sqlalchemy.orm import Session

from .auth import PortalUser
from .models import Activity


def log_activity(db: Session, user: PortalUser, action: str, detail: str = "") -> None:
    db.add(Activity(user_id=user.id, action=action, detail=detail[:2000]))
    db.commit()