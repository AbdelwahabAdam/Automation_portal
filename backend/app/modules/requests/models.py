"""The tables requests owns: a request, its files and its history."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ...core.database import Base


class Request(Base):
    __tablename__ = "requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    form_type: Mapped[str] = mapped_column(String(50), index=True)
    data: Mapped[dict] = mapped_column(JSONB)
    # draft -> submitted -> returned (to the owner, with a reason) or approved; returned -> submitted again
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    # Goes up each time the request is submitted, so a decision applies to the version that was reviewed
    revision: Mapped[int] = mapped_column(default=0, server_default="0")
    returned_reason: Mapped[str | None] = mapped_column(Text)
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # What approving the request created in Daftra lives in `request_documents` now, one row per
    # document, so a form that creates something else (a credit note, an estimate) needs no new
    # column. These seven are still written, because the release before this one reads them and a
    # rollback can put the old code back but not the database; the release after it drops them.
    # They are mapped under private names, and the public ones below read the table.
    _client_id: Mapped[int | None] = mapped_column("daftra_client_id")
    _invoice_id: Mapped[int | None] = mapped_column("daftra_invoice_id")
    _invoice_no: Mapped[str | None] = mapped_column("daftra_invoice_no", String(30))
    _payment_id: Mapped[int | None] = mapped_column("daftra_payment_id")
    _receipt_no: Mapped[str | None] = mapped_column("daftra_receipt_no", String(30))
    _work_order_id: Mapped[int | None] = mapped_column("daftra_work_order_id")
    _work_order_no: Mapped[str | None] = mapped_column("daftra_work_order_no", String(30))
    # These two are about the approval, not about one document, so they stay on the request
    daftra_error: Mapped[str | None] = mapped_column(Text)
    daftra_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Named, not imported: identity owns User, and no module imports another's models, so these
    # two carry no Mapped[...] annotation — SQLAlchemy resolves "User" from its own registry.
    created_by = relationship("User", foreign_keys=[created_by_id])

    @property
    def created_by_name(self) -> str:
        """How its owner is named wherever the request is shown."""
        owner = self.created_by
        return (owner.full_name or owner.username) if owner is not None else ""

    reviewed_by = relationship("User", foreign_keys=[reviewed_by_id])
    events: Mapped[list["RequestEvent"]] = relationship(
        back_populates="request", cascade="all, delete-orphan", order_by="RequestEvent.id"
    )
    attachments: Mapped[list["Attachment"]] = relationship(
        back_populates="request", cascade="all, delete-orphan", order_by="Attachment.id"
    )

    documents: Mapped[list["RequestDocument"]] = relationship(
        back_populates="request", cascade="all, delete-orphan", order_by="RequestDocument.id"
    )

    # ---------- What approving it created in Daftra ----------

    #: kind -> the two legacy columns it used to live in (id, number). A kind added since the
    #: documents became rows of their own — the estimate عرض السعر makes — has no column to keep.
    LEGACY = {
        "client": ("_client_id", None),
        "invoice": ("_invoice_id", "_invoice_no"),
        "payment": ("_payment_id", "_receipt_no"),
        "work_order": ("_work_order_id", "_work_order_no"),
    }
    NO_COLUMNS = (None, None)

    def document(self, kind: str) -> "RequestDocument | None":
        """The document of this kind, if approving has created it. One of each kind per request."""
        return next((row for row in self.documents if row.kind == kind), None)

    def doc_id(self, kind: str) -> int | None:
        """Daftra's id for it, or None if that step has not succeeded yet."""
        found = self.document(kind)
        return found.external_id if found is not None else None

    def doc_no(self, kind: str) -> str | None:
        """The number people read: invoice 06273, the receipt's, the work order's."""
        found = self.document(kind)
        return (found.number or None) if found is not None else None

    def save_document(self, kind: str, external_id: int | None, number: str | None = None):
        """Keeps what a step created, so approving again carries on from the step that failed.

        Writes the row and the legacy column it used to live in, until that column is dropped.
        """
        if external_id is None:
            self.forget_document(kind)
            return
        found = self.document(kind)
        if found is None:
            found = RequestDocument(request=self, kind=kind, external_id=int(external_id))
            self.documents.append(found)
        found.external_id = int(external_id)
        if number is not None:
            found.number = number or ""
        id_column, number_column = self.LEGACY.get(kind, self.NO_COLUMNS)
        if id_column is None:
            return
        setattr(self, id_column, int(external_id))
        if number_column and number is not None:
            setattr(self, number_column, number)

    def forget_document(self, kind: str):
        """Lets go of a document that turned out not to be this request's own."""
        found = self.document(kind)
        if found is not None:
            self.documents.remove(found)
        id_column, number_column = self.LEGACY.get(kind, self.NO_COLUMNS)
        if id_column is None:
            return
        setattr(self, id_column, None)
        if number_column:
            setattr(self, number_column, None)

    # The names everything above the model uses, and the API still answers
    @property
    def daftra_client_id(self) -> int | None:
        return self.doc_id("client")

    @property
    def daftra_invoice_id(self) -> int | None:
        return self.doc_id("invoice")

    @property
    def daftra_invoice_no(self) -> str | None:
        return self.doc_no("invoice")

    @property
    def daftra_payment_id(self) -> int | None:
        return self.doc_id("payment")

    @property
    def daftra_receipt_no(self) -> str | None:
        return self.doc_no("payment")

    @property
    def daftra_estimate_id(self) -> int | None:
        return self.doc_id("estimate")

    @property
    def daftra_estimate_no(self) -> str | None:
        return self.doc_no("estimate")

    @property
    def daftra_work_order_id(self) -> int | None:
        return self.doc_id("work_order")

    @property
    def daftra_work_order_no(self) -> str | None:
        return self.doc_no("work_order")


class RequestDocument(Base):
    """One document an approved request created in Daftra.

    One of each kind per request. A form that creates something else — a credit note for a
    return, an estimate for a quotation — adds a kind, not a column.
    """

    __tablename__ = "request_documents"
    # Deferred: letting go of a document and saving another of the same kind in one
    # transaction would otherwise insert the new row before the old one is deleted, and
    # hit this key. Checked at commit instead, where the invariant is what matters.
    __table_args__ = (
        UniqueConstraint("request_id", "kind", name="uq_request_documents_kind",
                         deferrable=True, initially="DEFERRED"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("requests.id", ondelete="CASCADE"), index=True)
    # client · invoice · payment · work_order · estimate — later credit_note, …
    kind: Mapped[str] = mapped_column(String(20))
    # Daftra's own id for it
    external_id: Mapped[int]
    # The number people read: invoice 06273, the receipt's, the work order's. Empty for a client.
    number: Mapped[str] = mapped_column(String(30), default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    request: Mapped["Request"] = relationship(back_populates="documents")

class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("requests.id", ondelete="CASCADE"), index=True)
    field: Mapped[str] = mapped_column(String(50))
    filename: Mapped[str] = mapped_column(String(255))
    stored_name: Mapped[str] = mapped_column(String(80))
    content_type: Mapped[str] = mapped_column(String(100))
    size: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    request: Mapped["Request"] = relationship(back_populates="attachments")


class RequestEvent(Base):
    """One step in a request's history: created, submitted, returned with a reason, approved."""

    __tablename__ = "request_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("requests.id", ondelete="CASCADE"), index=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    # Name at the time, kept if the user is later deleted
    username: Mapped[str] = mapped_column(String(120), default="")
    kind: Mapped[str] = mapped_column(String(30))
    revision: Mapped[int] = mapped_column(default=0)
    note: Mapped[str | None] = mapped_column(Text)

    request: Mapped["Request"] = relationship(back_populates="events")
