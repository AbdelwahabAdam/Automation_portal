"""Small helpers for the text and dates the portal reads and writes, shared by several modules."""

import re
from datetime import date, datetime, timedelta, timezone

# Arabic-Indic and Persian digits as Latin ones, for numbers typed on an Arabic keyboard
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
# The UAE has no daylight saving: always UTC+4
UAE = timezone(timedelta(hours=4))


def digits(raw) -> str:
    """Only the digits of a value, Arabic digits read as Latin ones (e.g. a phone or client code)."""
    return re.sub(r"\D", "", str(raw or "").translate(ARABIC_DIGITS))


def squash(text) -> str:
    """The text with surrounding spaces removed and inner runs of whitespace made one space."""
    return " ".join(str(text or "").split())


def uae_today() -> date:
    """Today's date in the UAE, whatever time zone the server runs in."""
    return datetime.now(UAE).date()


def day_month_year(day: str) -> str:
    """2026-10-19 (or 2026-10-19 10:30:00) as Daftra prints it, 19/10/2026; anything else unchanged."""
    found = re.match(r"(\d{4})-(\d{2})-(\d{2})", day or "")
    return f"{found[3]}/{found[2]}/{found[1]}" if found else day


def display_name(user) -> str:
    """How a user is named in emails, histories and Daftra documents."""
    return user.full_name or user.username
