"""What the terms tab and the package editor send in."""

from pydantic import BaseModel, Field


class TermIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    version: int = Field(ge=1, le=9999)
    body: str = Field(min_length=1, max_length=20000)


class PackageTermIn(BaseModel):
    # None: the package prints no terms
    term_id: int | None = None
