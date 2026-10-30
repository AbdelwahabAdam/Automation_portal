"""Who may see a request, change it, and decide on it — form by form.

Every rule here is about one request's own form: holding `form.new_sale.review` says nothing
about a technician's request. The server checks every call: hiding a button is never the check.
"""

from sqlalchemy.orm import Session

from ....core.errors import Conflict, Forbidden, NotFound
from ....core.permissions import REVIEW, SUBMIT, VIEW
from ... import form_engine
from ..models import Attachment, Request

# A request its owner may still change: a draft, or one returned for corrections
EDITABLE = ("draft", "returned")
# What the owner is told when they no longer hold the form they made the request with
LOST_ACCESS = "لم تعد لديك صلاحية تعبئة هذا النموذج، فلا يمكنك تعديل الطلب. تواصل مع مدير النظام."


def may(user, form_type: str, does: str) -> bool:
    return form_engine.may(user, form_type, does)


def can_view(request: Request, user) -> bool:
    """Its owner always — even after losing the form — and anyone holding view or review on that
    request's own form. A reviewer only reads a draft; only the owner can change one."""
    if request.created_by_id == user.id:
        return True
    return may(user, request.form_type, VIEW) or may(user, request.form_type, REVIEW)


def viewable(db: Session, request_id: int, user) -> Request:
    request = db.get(Request, request_id)
    if request is None or not can_view(request, user):
        raise NotFound("الطلب غير موجود")
    return request


def own(db: Session, request_id: int, user) -> Request:
    request = db.get(Request, request_id)
    if request is None or request.created_by_id != user.id:
        raise NotFound("الطلب غير موجود")
    return request


def check_may_submit(user, form_type: str):
    """What filling a form in takes. A form nobody has been granted is closed to everyone but admins."""
    if not may(user, form_type, SUBMIT):
        raise Forbidden("ليست لديك صلاحية تعبئة هذا النموذج")


def own_draft(db: Session, request_id: int, user) -> Request:
    """A request its owner may still change: a draft, or one returned for corrections.

    The owner can always open their own request, but changing one needs the form still.
    """
    request = own(db, request_id, user)
    if request.status not in EDITABLE:
        raise Conflict("الطلب مُرسل للمراجعة أو معتمد ولا يمكن تعديله")
    if not may(user, request.form_type, SUBMIT):
        raise Forbidden(LOST_ACCESS)
    return request


def own_unsent_draft(db: Session, request_id: int, user) -> Request:
    request = own(db, request_id, user)
    if request.status != "draft":
        raise Conflict("يمكن حذف المسودات فقط")
    if not may(user, request.form_type, SUBMIT):
        raise Forbidden(LOST_ACCESS)
    return request


def own_attachment(db: Session, attachment_id: int, user) -> Attachment:
    attachment = db.get(Attachment, attachment_id)
    if attachment is None or attachment.request.created_by_id != user.id:
        raise NotFound("المرفق غير موجود")
    return attachment


def viewable_attachment(db: Session, attachment_id: int, user) -> Attachment:
    attachment = db.get(Attachment, attachment_id)
    if attachment is None or not can_view(attachment.request, user):
        raise NotFound("المرفق غير موجود")
    return attachment


def can_review(request: Request, user) -> bool:
    return may(user, request.form_type, REVIEW)


def check_can_decide(request: Request, user, revision: int) -> Request:
    """A request a reviewer may decide on: one of their forms, still waiting, the version they
    looked at, and not their own."""
    if request is None or request.status == "draft":
        raise NotFound("الطلب غير موجود")
    if not can_review(request, user):
        # Not theirs to decide: the same answer as a request that is not there, so holding no
        # review on a form does not reveal that one of its requests exists
        raise NotFound("الطلب غير موجود")
    if request.status != "submitted":
        raise Conflict("تمت مراجعة هذا الطلب بالفعل. حدّث الصفحة لرؤية حالته الحالية.")
    if request.revision != revision:
        raise Conflict("تغيّر الطلب منذ فتحته. حدّث الصفحة وراجع النسخة الحالية.")
    # A manager does not decide on their own request; the system admin can
    if request.created_by_id == user.id and not user.is_admin:
        raise Forbidden("لا يمكنك مراجعة طلب أرسلته بنفسك. يراجعه مدير آخر.")
    return request


def reviewable_form_keys(user) -> list[str]:
    """The forms whose requests this user may see in المراجعة: those they may view or review."""
    keys = [spec.key for spec in form_engine.forms_for(user, VIEW)]
    keys += [spec.key for spec in form_engine.forms_for(user, REVIEW) if spec.key not in keys]
    # Kept in the forms' own order, which is the order of النماذج
    return [spec.key for spec in form_engine.all_forms() if spec.key in set(keys)]
