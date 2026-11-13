"""The contract every form fills in, and the two contexts the engine hands its hooks.

The engine never names a form: it knows only what a `FormSpec` says. A form that behaves like
every other one is a `FormSpec` and its fields, and nothing else.
"""

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class FormAction:
    """Something a request of this form can be made to do after it is approved, from its own page
    (e.g. «إنشاء أمر الشغل» on a request waiting for its payment). Its owner or a reviewer of the
    form may run it."""

    key: str
    label: str
    statuses: tuple[str, ...]
    """The request statuses it is offered in."""

    run: Callable
    """(ctx: ApprovalContext, values: dict) -> a summary for the activity log. Raises Invalid
    (with fields) for values it will not take, and SyncError when Daftra fails."""

    fields: tuple[dict, ...] = ()
    """What it asks for first, as form fields (only plain inputs: number, text, date)."""

    confirm: str = ""
    """What the dialog says before it runs."""

    then_status: str | None = None
    """The status the request moves to once it has run; None keeps the one it has."""

    def as_api(self) -> dict:
        return {"key": self.key, "label": self.label, "statuses": list(self.statuses),
                "fields": list(self.fields), "confirm": self.confirm}


@dataclass(frozen=True)
class FormSpec:
    """One form, as its folder declares it."""

    key: str
    """Stored on every request: never rename one."""

    label: str
    icon: str
    description: str
    sections: list[dict]
    visible: bool = True
    """False: no new requests; old ones still open and can be reviewed."""

    ready: bool = True
    """False: in the catalog, but greyed out and not clickable — a form staff can see is coming
    without being able to start one yet. Unlike visible=False, which leaves it out altogether."""

    daftra_note: str = ""
    """What the form tells the user approving it will create in Daftra."""

    validate: Callable | None = None
    """(data, ctx) -> {field: message}: the checks the field rules cannot express."""

    on_approve: Callable | None = None
    """(ctx) -> a summary for the activity log: what approving creates outside the portal."""

    approved_status: str = "approved"
    """Where approving leaves a request: «approved», its end, unless the form has more to wait
    for (e.g. «awaiting_payment»), which its actions then carry on from."""

    actions: tuple[FormAction, ...] = ()
    """What can be done to one of its requests after approval (see FormAction)."""

    def action(self, key: str) -> "FormAction | None":
        return next((action for action in self.actions if action.key == key), None)

    @property
    def invoiced(self) -> bool:
        """Whether approving it creates anything in Daftra. `RequestView.jsx` reads this."""
        return self.on_approve is not None

    def fields(self) -> list[dict]:
        """Every field of the form, section by section."""
        return [spec for section in self.sections for spec in section["fields"]]

    def as_api(self, may: dict | None = None) -> dict:
        """The form as `GET /api/form-types` gives it, with what this user may do with it."""
        return {"key": self.key, "label": self.label, "icon": self.icon, "description": self.description,
                "sections": self.sections, "invoiced": self.invoiced, "daftra_note": self.daftra_note,
                "hidden": not self.visible, "disabled": not self.ready,
                "actions": [action.as_api() for action in self.actions],
                **(may or {})}


# `Any` throughout: form_engine knows nothing about the requests or identity modules.
@dataclass
class CheckContext:
    """What a form's `validate` is given besides the data."""

    db: Any
    user: Any = None
    choices: dict = field(default_factory=dict)
    """What the form's list fields offered, by field type; one that could not be loaded is left out."""


@dataclass
class ApprovalContext:
    """What a form's `on_approve` is given."""

    request: Any
    """What is created is kept on it, step by step, so approving again carries on from the failed step."""

    db: Any
    reviewer: Any = None
    """The approving user, the receipt's المستلم."""

    @property
    def data(self) -> dict:
        """The request's fields, as the form's output.py reads them: ctx.data["paid_amount"]."""
        return self.request.data
