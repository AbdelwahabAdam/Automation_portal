"""The activity-log page: the filters behind it, a page of entries, and the CSV export."""

import csv
import io
import json
from datetime import date

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...core.text import UAE
from ...core.security import require
from . import repo
from .labels import ACTIONS, ENTITY_TYPES, field_labels, value_labels
from .schemas import AuditPage
from .service import Audit, users_for_filter

# More rows than this would be a file nobody opens, and a query nobody waits for
EXPORT_LIMIT = 20000
PAGE_LIMIT = 200

may_read = require("admin.audit")
router = APIRouter(prefix="/api/admin", dependencies=[Depends(may_read)])


def conditions(user_id: int | None = None, action: str = "", entity_type: str = "",
               date_from: date | None = None, date_to: date | None = None, search: str = "") -> list:
    return repo.filters(user_id, action, entity_type, date_from, date_to, search)


@router.get("/audit/options")
def audit_options(db: Session = Depends(get_db)):
    """The lists behind the audit log filters and the labels used to display an entry."""
    return {
        "actions": ACTIONS,
        "entity_types": ENTITY_TYPES,
        "field_labels": field_labels(),
        "value_labels": value_labels(),
        "users": users_for_filter(db),
    }


@router.get("/audit", response_model=AuditPage)
def list_audit(found: list = Depends(conditions), limit: int = 50, offset: int = 0,
               db: Session = Depends(get_db)):
    limit = max(1, min(limit, PAGE_LIMIT))
    return {"total": repo.count(db, found), "items": repo.page(db, found, limit, max(0, offset))}


@router.get("/audit/export")
def export_audit(found: list = Depends(conditions), admin=Depends(may_read),
                 db: Session = Depends(get_db), audit: Audit = Depends()):
    """The filtered log as a CSV file that Excel opens directly."""
    entries = repo.page(db, found, EXPORT_LIMIT, 0)

    def values(data: dict | None) -> str:
        if not data:
            return ""
        return json.dumps({field_labels().get(k, k): v for k, v in data.items()}, ensure_ascii=False)

    def cell(value: str) -> str:
        # Excel would run a cell starting with one of these as a formula
        return "'" + value if value[:1] in ("=", "+", "-", "@") else value

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["الوقت (توقيت الإمارات)", "المستخدم", "الإجراء", "نوع السجل", "السجل",
                     "القيم قبل", "القيم بعد", "عنوان IP", "المتصفح"])
    for entry in entries:
        writer.writerow([
            entry.at.astimezone(UAE).strftime("%Y-%m-%d %H:%M:%S"), cell(entry.username),
            ACTIONS.get(entry.action, entry.action), ENTITY_TYPES.get(entry.entity_type, entry.entity_type),
            cell(entry.entity_label), values(entry.before), values(entry.after), entry.ip, cell(entry.user_agent),
        ])
    audit.log(admin, "audit.export", after={"rows": len(entries)})
    db.commit()
    # The BOM makes Excel read the file as UTF-8
    return Response(
        "﻿" + out.getvalue(), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="audit-log.csv"'},
    )
