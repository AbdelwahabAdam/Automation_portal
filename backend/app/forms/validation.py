"""Checking a submitted request against its form, and keeping a draft as typed."""

import math
import re
from datetime import date

from ..text import ARABIC_DIGITS, uae_today
from .definitions import form_fields
from .options import package_colors, package_quantity

PHONE_RE = re.compile(r"^(?:\+?971|0)\d{8,9}$")
# Field type "product" holds a name picked from our catalog, "staff" one picked from Daftra's staff list
DEFAULT_MAX_LENGTH = {"text": 300, "product": 300, "staff": 300, "textarea": 3000, "package_color": 300}
# Field types holding the id of a row in a Daftra list; the form shows the list, the data keeps the
# id in the field and the row's name in "<field>_name"
DAFTRA_LIST_TYPES = ("daftra_order_source", "daftra_treasury", "daftra_client_category", "daftra_client_invoice")


def is_input(spec: dict) -> bool:
    """True for fields the user types into (not uploads, computed or automatic ones)."""
    return spec["type"] not in ("files", "auto_user") and "computed" not in spec


def _clean_value(spec: dict, raw):
    """Returns (value, error) for one input field. An empty value comes back as None."""
    kind = spec["type"]
    if kind == "multiselect":
        chosen = [v for v in raw if v in spec["options"]] if isinstance(raw, list) else []
        return (chosen or None), None
    if kind == "order_lines":
        lines = []
        for line in raw if isinstance(raw, list) else []:
            if not isinstance(line, dict):
                continue
            product_id = str(line.get("product_id") or "").strip()
            try:
                quantity = int(line.get("quantity"))
            except (TypeError, ValueError):
                quantity = 0
            if product_id and quantity > 0:
                package_id = str(line.get("package_id") or "").strip()
                lines.append({
                    "product_id": product_id, "name": str(line.get("name") or "")[:200], "quantity": quantity,
                    # Lines picked from the same package keep this, so the form can group them back together
                    "group_id": str(line["group_id"])[:40] if line.get("group_id") else None,
                    "group_name": str(line.get("group_name") or "")[:200],
                    # The package the line was picked from, which sets its price (see validate_submission)
                    "package_id": package_id if package_id.isdigit() else None,
                    "base_quantity": int(line["base_quantity"]) if str(line.get("base_quantity") or "").isdigit() else None,
                    # Raw per-line fields (e.g. design, cooler colour); validated in validate_submission,
                    # against this field's own "line_fields", since each line needs its own errors
                    "details": line.get("details") if isinstance(line.get("details"), dict) else {},
                })
        return (lines or None), None

    value = "" if raw is None or isinstance(raw, (list, dict)) else str(raw).strip()
    if value == "":
        return None, None

    if kind == "number":
        try:
            number = float(value.translate(ARABIC_DIGITS).replace(",", ""))
        except ValueError:
            return None, "أدخل رقمًا صحيحًا"
        # "inf" and "nan" read as numbers, but are no amount and cannot be stored
        if not math.isfinite(number):
            return None, "أدخل رقمًا صحيحًا"
        if spec.get("integer") and not number.is_integer():
            return None, "أدخل عددًا بدون كسور"
        if spec.get("positive") and number <= 0:
            return None, "يجب أن يكون أكبر من صفر"
        if "min" in spec and number < spec["min"]:
            return None, f"الحد الأدنى {spec['min']}"
        if "max" in spec and number > spec["max"]:
            return None, f"الحد الأقصى {spec['max']}"
        return (int(number) if spec.get("integer") else round(number, 2)), None
    if kind == "phone":
        value = re.sub(r"[\s\-()]", "", value.translate(ARABIC_DIGITS))
        return (value, None) if PHONE_RE.match(value) else (None, "أدخل رقم هاتف إماراتي صحيح")
    if kind == "date":
        try:
            parsed = date.fromisoformat(value)
        except ValueError:
            return None, "أدخل تاريخًا صحيحًا"
        # The UAE's today: the server's clock (UTC) is still on yesterday until 4 a.m. there
        if spec.get("not_future") and parsed > uae_today():
            return None, "التاريخ لا يمكن أن يكون في المستقبل"
        return value, None
    if kind == "select":
        return (value, None) if value in spec["options"] else (None, "اختر من القائمة")
    if kind in DAFTRA_LIST_TYPES:
        # Checked against Daftra's list in validate_submission, when the list could be loaded
        return (int(value), None) if value.isdigit() else (None, "اختر من القائمة")

    if len(value) > spec.get("max_length", DEFAULT_MAX_LENGTH[kind]):
        return None, f"الحد الأقصى {spec.get('max_length', DEFAULT_MAX_LENGTH[kind])} حرفًا"
    if "pattern" in spec:
        value = value.translate(ARABIC_DIGITS)
        if not re.match(spec["pattern"], value):
            return None, spec.get("pattern_message", "صيغة غير صحيحة")
    return value, None


def _condition_met(condition: dict, clean: dict) -> bool:
    value = clean.get(condition["field"])
    if "equals" in condition:
        return value == condition["equals"]
    if "in" in condition:
        return value in condition["in"]
    if "not_in" in condition:
        return value not in condition["not_in"]
    return isinstance(value, (int, float)) and value > condition["gt"]


def validate_submission(form_type: str, data: dict, file_counts: dict, employee_name: str,
                        products: dict | None = None, package_prices: dict | None = None,
                        daftra_lists: dict | None = None) -> tuple[dict, dict]:
    """Returns (clean_data, errors) where errors maps field name to message.

    products maps our catalog's product id to product; None means the list could not be loaded,
    in which case the product the user picked is accepted as sent.
    package_prices maps (package id, product id) to the product's unit price inside that package.
    daftra_lists maps a DAFTRA_LIST_TYPES type to {id: name} of Daftra's list; a type missing from
    it could not be loaded, so its id is accepted as sent and Daftra checks it on approval.
    """
    fields = form_fields(form_type)
    clean, errors = {}, {}

    for spec in filter(is_input, fields):
        value, error = _clean_value(spec, data.get(spec["name"]))
        if error:
            errors[spec["name"]] = error
        elif value is not None:
            clean[spec["name"]] = value

    for spec in fields:
        name = spec["name"]
        if spec["type"] != "product" or name not in clean:
            continue
        product_id = str(data.get(name + "_id") or "").strip()
        product = products.get(product_id) if products is not None else None
        if products is not None and product is None:
            del clean[name]
            errors[name] = "اختر المنتج من القائمة"
        elif product_id:
            clean[name + "_id"] = product_id
            if product:
                clean[name] = product["name"]

    for spec in fields:
        name = spec["name"]
        if spec["type"] != "order_lines" or name not in clean:
            continue
        line_fields = spec.get("line_fields", [])
        charges = [dspec["name"] for dspec in line_fields if dspec.get("charge")]
        resolved = []
        line_errors = {}
        subtotal = 0.0
        seen_groups = set()
        for index, line in enumerate(clean[name]):
            product = products.get(line["product_id"]) if products is not None else None
            if products is not None and product is None:
                continue
            # A field offering only maintenance items takes nothing else, whatever the browser sends
            if spec.get("items") == "maintenance" and product is not None and not product.get("maintenance_group"):
                continue
            # The price is looked up here, never taken from the browser: a product's price inside the
            # package it was picked from, else its own catalog price
            price = None
            if line["package_id"] and package_prices is not None:
                price = package_prices.get((line["package_id"], line["product_id"]))
            if price is None and product:
                price = product.get("price") or 0
            # A package's «الكمية» is already in its products' quantities; its charges (the inscription) are per package
            count = package_quantity(line)
            subtotal += (price or 0) * line["quantity"]
            details, row_errors = {}, {}
            for dspec in filter(is_input, line_fields):
                dvalue, derror = _clean_value(dspec, line["details"].get(dspec["name"]))
                if derror:
                    row_errors[dspec["name"]] = derror
                elif dvalue is not None:
                    details[dspec["name"]] = dvalue
            for dspec in line_fields:
                dname = dspec["name"]
                required = dspec["required"] or ("required_if" in dspec and _condition_met(dspec["required_if"], details))
                if dspec["type"] == "package_color":
                    # The package (or the product picked on its own) decides the choices, and whether there are any
                    allowed = [shown for shown, _ in package_colors(line.get("group_name") or line.get("name"))]
                    required = bool(allowed) and not dspec.get("optional")
                    if dname in details and details[dname] not in allowed:
                        if allowed:
                            row_errors[dname] = "اختر من القائمة"
                        del details[dname]
                if required and dname not in details and dname not in row_errors:
                    row_errors[dname] = "مطلوب"
            if row_errors:
                line_errors[str(len(resolved))] = row_errors
            # A package's details are copied onto each of its lines, so its charges count once
            if not line.get("group_id") or line["group_id"] not in seen_groups:
                subtotal += sum(details.get(charge) or 0 for charge in charges) * count
            if line.get("group_id"):
                seen_groups.add(line["group_id"])
            resolved.append({
                "product_id": line["product_id"], "name": product["name"] if product else line["name"],
                "quantity": line["quantity"], "group_id": line.get("group_id"), "group_name": line.get("group_name"),
                "package_id": line["package_id"], "base_quantity": line.get("base_quantity"), "unit_price": price,
                "details": details,
            })
        if not resolved:
            del clean[name]
            errors[name] = "اختر منتجًا أو باقة واحدة على الأقل"
        else:
            clean[name] = resolved
            if line_errors:
                errors[name] = {"lines": line_errors}
            # The field named here shows this total, worked out from each line's catalog price
            if spec.get("subtotal_field") and products is not None:
                clean[spec["subtotal_field"]] = round(subtotal, 2)

    for spec in fields:
        name = spec["name"]
        options = (daftra_lists or {}).get(spec["type"])
        if spec["type"] not in DAFTRA_LIST_TYPES or name not in clean or options is None:
            continue
        if clean[name] in options:
            clean[name + "_name"] = options[clean[name]]
        else:
            del clean[name]
            errors[name] = "اختر من القائمة"

    for spec in fields:
        name = spec["name"]
        if spec["type"] == "auto_user":
            clean[name] = employee_name
        elif "computed" in spec:
            # Already set by something else (e.g. order_lines' subtotal_field); nothing to subtract here
            if name in clean or not spec["computed"]:
                continue
            first, *rest = (clean.get(operand) for operand in spec["computed"])
            if first is not None:
                result = round(first - sum(v or 0 for v in rest), 2)
                if result < 0:
                    errors[name] = spec["negative_message"]
                else:
                    clean[name] = result

    # A field that must equal another (e.g. the amount paid must be the whole total)
    for spec in fields:
        other = spec.get("must_equal")
        if other and spec["name"] in clean and other in clean and spec["name"] not in errors:
            if abs(clean[spec["name"]] - clean[other]) > 0.005:
                errors[spec["name"]] = spec.get("must_equal_message") or "القيمتان يجب أن تتساويا"

    for spec in fields:
        name = spec["name"]
        required = spec["required"] or ("required_if" in spec and _condition_met(spec["required_if"], clean))
        if not required or name in errors:
            continue
        if spec["type"] == "files":
            if not file_counts.get(name):
                errors[name] = "أرفق ملفًا واحدًا على الأقل"
        elif is_input(spec) and name not in clean:
            errors[name] = "مطلوب"
    return clean, errors


def _dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _finite(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def sanitize_draft(form_type: str, data: dict) -> dict:
    """Drafts are stored as typed, without validation, so the user can finish them later."""
    draft = {}
    for spec in filter(is_input, form_fields(form_type)):
        raw = data.get(spec["name"])
        if spec["type"] == "order_lines":
            lines = [
                {"product_id": str(line.get("product_id"))[:20], "name": str(line.get("name") or "")[:200],
                 "quantity": int(line["quantity"]) if str(line.get("quantity", "")).strip().isdigit() else 1,
                 "group_id": str(line["group_id"])[:40] if line.get("group_id") else None,
                 "group_name": str(line.get("group_name") or "")[:200],
                 "package_id": str(line["package_id"])[:20] if str(line.get("package_id") or "").isdigit() else None,
                 "base_quantity": int(line["base_quantity"]) if str(line.get("base_quantity") or "").isdigit() else None,
                 # Shown again when the draft is opened; worked out afresh when it is submitted
                 "unit_price": line["unit_price"] if _finite(line.get("unit_price")) else None,
                 "details": {
                     str(k)[:40]: str(v)[:2000] for k, v in _dict(line.get("details")).items()
                     if not isinstance(v, (list, dict))
                 }}
                for line in (raw if isinstance(raw, list) else [])[:100]
                if isinstance(line, dict) and line.get("product_id")
            ]
            if lines:
                draft[spec["name"]] = lines
            continue
        if isinstance(raw, list):
            value = [str(v)[:200] for v in raw[:50]]
        else:
            value = "" if raw is None or isinstance(raw, dict) else str(raw)[:5000]
        if value:
            draft[spec["name"]] = value
            if spec["type"] == "product" and data.get(spec["name"] + "_id"):
                draft[spec["name"] + "_id"] = str(data[spec["name"] + "_id"])[:20]
            if spec["type"] in DAFTRA_LIST_TYPES and data.get(spec["name"] + "_name"):
                draft[spec["name"] + "_name"] = str(data[spec["name"] + "_name"])[:200]
    return draft
