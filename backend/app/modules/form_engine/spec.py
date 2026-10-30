"""The contract every form fills in, and the two contexts the engine hands its hooks.

The engine never names a form: it knows only what a `FormSpec` says. A form that behaves like
every other one is a `FormSpec` and its fields, and nothing else.
"""

from dataclasses import dataclass, field
from typing import Any, Callable


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

    daftra_note: str = ""
    """What the form tells the user approving it will create in Daftra."""

    validate: Callable | None = None
    """(data, ctx) -> {field: message}: the checks the field rules cannot express."""

    on_approve: Callable | None = None
    """(ctx) -> a summary for the activity log: what approving creates outside the portal."""

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
                "hidden": not self.visible, **(may or {})}


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
