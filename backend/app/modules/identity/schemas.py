"""The shapes identity takes in and gives back."""

from pydantic import BaseModel, ConfigDict, Field


class LoginIn(BaseModel):
    # Email or username
    username: str
    password: str
    # The 6-digit code from the email, once the server has sent it
    code: str = ""


class ForgotIn(BaseModel):
    username: str


class SetPasswordIn(BaseModel):
    token: str
    # bcrypt reads at most 72 bytes of a password
    password: str = Field(min_length=8, max_length=72)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str | None
    full_name: str
    is_admin: bool
    # The permission keys this user holds, so a screen can hide what they cannot do
    permissions: list[str] = []
    # The menu groups and pages this user can open, in menu order, each with its path
    navigation: list[dict]
    # On: nothing reaches Daftra, and every page shows a strip saying so
    daftra_fake: bool = False


class LoginOut(BaseModel):
    # True, with no token, when the password was right and a code has been emailed
    mfa_required: bool = False
    # Where the code went, partly hidden, and how long before another can be sent
    email_hint: str | None = None
    resend_in: int | None = None
    access_token: str | None = None
    user: UserOut | None = None
