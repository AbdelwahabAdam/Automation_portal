"""What the request screens send and receive."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RequestIn(BaseModel):
    form_type: str
    data: dict
    action: Literal["draft", "submit"]


class RequestUpdate(BaseModel):
    data: dict
    action: Literal["draft", "submit"]


class AttachmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    field: str
    filename: str
    content_type: str
    size: int


class RequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    form_type: str
    data: dict
    status: str
    revision: int
    returned_reason: str | None
    created_at: datetime
    updated_at: datetime
    submitted_at: datetime | None
    reviewed_at: datetime | None
    # Whose request it is: a reviewer opening it by URL has no list row to read it from
    created_by_id: int
    created_by_name: str = ""
    attachments: list[AttachmentOut]
    daftra_invoice_no: str | None
    daftra_receipt_no: str | None
    daftra_work_order_no: str | None
    daftra_estimate_no: str | None
    daftra_error: str | None
    daftra_synced_at: datetime | None


class DecisionIn(BaseModel):
    # The revision the reviewer looked at; a request changed since then is refused
    revision: int


class ReturnIn(DecisionIn):
    reason: str = Field(min_length=1, max_length=2000)
