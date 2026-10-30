"""What the activity-log page sends and receives."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    at: datetime
    user_id: int | None
    username: str
    action: str
    entity_type: str
    entity_id: int | None
    entity_label: str
    before: dict | None
    after: dict | None
    ip: str
    user_agent: str


class AuditPage(BaseModel):
    total: int
    items: list[AuditOut]
