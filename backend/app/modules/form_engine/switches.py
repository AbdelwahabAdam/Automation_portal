"""The switch every field of a section takes: whether the form shows it, and whether it must be filled.

    HIDE                 not on this form at all
    SHOW                 on the form, may be left empty
    REQUIRED             on the form, must be filled
    REQUIRED_IF(when)    on the form, must be filled when `when` holds, e.g. REQUIRED_IF(DISCOUNTED)

    NEW_CLIENT(switch)   the same, but only while the phone search has found no client: a field
                         Daftra asks of a client it is creating, and already has for one it knows

A section is a function with one keyword argument per field, each taking one of these:

    client(phone=REQUIRED, phone2=SHOW, client_code=HIDE, ...)

So what a form asks for is read in the form's own file, one line per field, rather than worked
out from flags inside a helper. What a field *is* — its type, its pattern, how it is computed —
stays in the section: a form decides whether a field appears and whether it must be filled, not
how a phone number is checked.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Switch:
    kind: str
    when: dict | None = None
    new_client: bool = False

    def __repr__(self) -> str:
        shown = f"REQUIRED_IF({self.when!r})" if self.kind == "required_if" else self.kind.upper()
        return f"NEW_CLIENT({shown})" if self.new_client else shown


HIDE = Switch("hide")
SHOW = Switch("show")
REQUIRED = Switch("required")


def REQUIRED_IF(when: dict) -> Switch:  # noqa: N802 — read as one of the four values, like HIDE
    """Must be filled when `when` holds: {"field": …, "equals" | "in" | "not_in" | "gt": …}."""
    if not isinstance(when, dict) or "field" not in when:
        raise ValueError(f"REQUIRED_IF takes a condition on another field, not {when!r}")
    return Switch("required_if", when)


def NEW_CLIENT(switch: Switch) -> Switch:  # noqa: N802
    """Asked only of a client the phone search has not found (validation's `new_client`)."""
    if not isinstance(switch, Switch) or switch.kind == "hide":
        raise ValueError("NEW_CLIENT wraps SHOW, REQUIRED or REQUIRED_IF")
    return Switch(switch.kind, switch.when, new_client=True)


def check(name: str, switch) -> Switch:
    """The switch given for a field, refused if it is not one: a True or a "show" is a mistake."""
    if not isinstance(switch, Switch):
        raise TypeError(f"{name}= takes HIDE, SHOW, REQUIRED or REQUIRED_IF(…), not {switch!r}")
    return switch


def shown(switch: Switch) -> bool:
    return switch.kind != "hide"


def required(switch: Switch) -> bool:
    """Required outright — not only under a condition."""
    return switch.kind == "required"


def apply(switch: Switch, field: dict) -> dict | None:
    """The field as this form has it, or None when the form leaves it out.

    The field's own `required` and `required_if` are replaced: the switch is the only word on it.
    """
    if switch.kind == "hide":
        return None
    out = {key: value for key, value in field.items() if key != "required_if"}
    out["required"] = switch.kind == "required"
    if switch.kind == "required_if":
        out["required_if"] = switch.when
    if switch.new_client:
        out["new_client"] = True
    return out


def switched_fields(*pairs) -> list[dict]:
    """(switch, field) pairs as a list of the fields the form keeps, in order.

    For fields that are not a section of their own — the fields of an order line, which the
    order_lines field carries as its line_fields.
    """
    fields = []
    for switch, field in pairs:
        made = apply(check(field["name"], switch), field)
        if made is not None:
            fields.append(made)
    return fields


def switched(title: str, *pairs, note: str | None = None) -> dict:
    """A section from (switch, field) pairs, in order, leaving out the hidden ones.

    For a section only one form has, written in that form's own `fields.py`:

        def installation(*, create_work_order, installation_days):
            return switched("التركيب وأمر الشغل",
                            (create_work_order, yes_no("create_work_order", "…")),
                            (installation_days, f("installation_days", "…", "number")))
    """
    return {"title": title, "note": note, "fields": switched_fields(*pairs)}
