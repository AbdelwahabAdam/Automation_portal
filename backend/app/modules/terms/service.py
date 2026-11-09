"""The terms texts, which one each package prints, and the one an invoice prints."""

import html

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...core.context import Actor
from ...core.errors import Conflict, Invalid, NotFound
from .. import catalog
from ..audit import log as audit_log
from ..requests import Request
from .models import PackageTerm, Term
from .schemas import PackageTermIn, TermIn


# ---------- What an invoice prints ----------


def as_html(body: str) -> str:
    """The text as Daftra's html_notes takes it: a bold paragraph per line, and an empty line as
    the empty paragraph Daftra's own editor makes (how invoice 06296's terms were written)."""
    lines = body.replace("\r\n", "\n").strip("\n").split("\n")
    return "".join(f"<p><b>{html.escape(line.strip())}</b></p>" if line.strip() else "<p><b><br></b></p>"
                   for line in lines)


def package_ids(data: dict) -> list[int]:
    """The packages the request's order lines come from, in the order they were added."""
    found = []
    for line in data.get("order_lines") or []:
        value = str(line.get("package_id") or "")
        if value.isdigit() and int(value) not in found:
            found.append(int(value))
    return found


def chosen_for(db: Session, data: dict) -> Term | None:
    """The term the request's invoice (or estimate) prints: that of the first package added to it
    that has one. None: none of its packages has terms, so it prints none."""
    packages = package_ids(data)
    if not packages:
        return None
    links = {link.package_id: link for link in db.scalars(select(PackageTerm).where(PackageTerm.package_id.in_(packages)))}
    first = next((links[package_id] for package_id in packages if package_id in links), None)
    return first.term if first is not None else None


# ---------- The terms tab ----------


def term_out(term: Term, assigned: int = 0, printed: int = 0) -> dict:
    return {"id": term.id, "name": term.name, "version": term.version, "label": term.label, "body": term.body,
            "created_at": term.created_at, "assigned": assigned, "printed": printed}


def _counts(db: Session, column) -> dict[int, int]:
    return dict(db.execute(select(column, func.count()).where(column.is_not(None)).group_by(column)).all())


def listed_terms(db: Session) -> list[dict]:
    assigned = _counts(db, PackageTerm.term_id)
    printed = _counts(db, Request.printed_terms_id)
    terms = db.scalars(select(Term).order_by(Term.name, Term.version.desc()))
    return [term_out(term, assigned.get(term.id, 0), printed.get(term.id, 0)) for term in terms]


def create_term(db: Session, who: Actor, body: TermIn) -> dict:
    name = " ".join(body.name.split())
    text = body.body.replace("\r\n", "\n").strip()
    if not name or not text:
        raise Invalid("اكتب اسم الشروط ونصها")
    if db.scalar(select(Term.id).where(Term.name == name, Term.version == body.version)) is not None:
        raise Conflict(f"الإصدار {body.version} من «{name}» موجود؛ اختر رقم إصدار آخر.")
    term = Term(name=name, version=body.version, body=text, created_by_id=who.user.id if who.user else None)
    db.add(term)
    db.flush()
    audit_log(db, who, "terms.create", "terms", term.id, term.label,
              after={"name": name, "version": body.version, "body": text})
    db.commit()
    return term_out(term)


def delete_term(db: Session, who: Actor, term_id: int):
    """Only a term no package prints and no invoice has printed: otherwise a request could no
    longer say what its invoice carries."""
    term = db.get(Term, term_id)
    if term is None:
        raise NotFound("الشروط غير موجودة")
    if db.scalar(select(func.count()).where(PackageTerm.term_id == term.id)):
        raise Conflict("الشروط مختارة لباقات. غيّرها في تلك الباقات أولًا.")
    if db.scalar(select(func.count()).where(Request.printed_terms_id == term.id)):
        raise Conflict("طُبعت هذه الشروط على فواتير، فتبقى ليُعرف ما طُبع عليها.")
    audit_log(db, who, "terms.delete", "terms", term.id, term.label,
              before={"name": term.name, "version": term.version})
    db.delete(term)
    db.commit()


# ---------- Each package's term (chosen in the package's own editor) ----------


def package_terms(db: Session) -> dict[int, int]:
    """{package id: term id} for every package that prints terms."""
    return dict(db.execute(select(PackageTerm.package_id, PackageTerm.term_id)).all())


def set_package_term(db: Session, who: Actor, package_id: int, body: PackageTermIn) -> dict:
    package = catalog.repo.package(db, package_id)
    if package is None:
        raise NotFound("الباقة غير موجودة")
    if body.term_id is not None and db.get(Term, body.term_id) is None:
        raise Invalid("الشروط غير موجودة")
    link = db.get(PackageTerm, package_id)
    before = link.term_id if link else None
    if body.term_id is None:
        if link is not None:
            db.delete(link)
    elif link is None:
        db.add(PackageTerm(package_id=package_id, term_id=body.term_id))
    else:
        link.term_id = body.term_id
    if before != body.term_id:
        audit_log(db, who, "terms.package", "package", package.id, package.name,
                  before={"term_id": before}, after={"term_id": body.term_id})
    db.commit()
    return {"package_id": package_id, "term_id": body.term_id}
