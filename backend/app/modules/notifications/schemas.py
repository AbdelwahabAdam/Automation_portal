"""What the mail test page sends."""

from pydantic import BaseModel


class MailTestIn(BaseModel):
    template: str
    to: str
