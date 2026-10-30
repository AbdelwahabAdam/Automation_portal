"""The emails the portal sends, their templates, and the page that tests them."""

from ..audit import add_value_labels
from . import service
from .router import router
from .service import (EMAILS, MailError, compose, compose_sample, is_configured, render, send,
                      send_login_code, send_password_link)

# How an email's name reads in the activity log. Added here, so audit does not import this module.
add_value_labels({key: email["label"] for key, email in EMAILS.items()})

__all__ = ["EMAILS", "MailError", "compose", "compose_sample", "is_configured", "render", "router",
           "send", "send_login_code", "send_password_link", "service"]
