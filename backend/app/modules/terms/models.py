"""The tables terms owns: the terms texts, and which one each package prints."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ...core.database import Base


class Term(Base):
    """One version of a terms text, e.g. «شروط وأحكام الضمان» version 2. Never changed once saved:
    a change is a new version, so a request always says what its invoice printed."""

    __tablename__ = "terms"
    __table_args__ = (UniqueConstraint("name", "version", name="uq_terms_name_version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    version: Mapped[int]
    # Plain text, a paragraph per line; printed on the invoice's last page (Daftra's html_notes)
    body: Mapped[str] = mapped_column(Text)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @property
    def label(self) -> str:
        return f"{self.name} — الإصدار {self.version}"


class PackageTerm(Base):
    """The term a package prints wherever it is sold (طلب بيع, طلب عرض سعر). A package without
    one prints none. Kept here rather than on the package: the catalog knows nothing of terms."""

    __tablename__ = "package_terms"

    package_id: Mapped[int] = mapped_column(ForeignKey("packages.id", ondelete="CASCADE"), primary_key=True)
    term_id: Mapped[int] = mapped_column(ForeignKey("terms.id", ondelete="RESTRICT"), index=True)

    term: Mapped[Term] = relationship()
