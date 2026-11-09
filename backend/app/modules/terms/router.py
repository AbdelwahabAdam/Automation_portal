"""The catalog page's terms tab, and each package's term. Transport only."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ...core.context import Actor
from ...core.database import get_db
from ...core.security import acting, require
from . import service
from .schemas import PackageTermIn, TermIn

# The catalog page's, so the catalog's own permission
may_keep = require("admin.catalog")
router = APIRouter(prefix="/api/admin/terms", dependencies=[Depends(may_keep)])


@router.get("")
def list_terms(db: Session = Depends(get_db)):
    return service.listed_terms(db)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_term(body: TermIn, who: Actor = Depends(acting(may_keep)), db: Session = Depends(get_db)):
    return service.create_term(db, who, body)


@router.delete("/{term_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_term(term_id: int, who: Actor = Depends(acting(may_keep)), db: Session = Depends(get_db)):
    service.delete_term(db, who, term_id)


@router.get("/packages")
def package_terms(db: Session = Depends(get_db)):
    """{package id: term id}; a package missing from it prints no terms."""
    return service.package_terms(db)


@router.put("/packages/{package_id}")
def set_package_term(package_id: int, body: PackageTermIn, who: Actor = Depends(acting(may_keep)),
                     db: Session = Depends(get_db)):
    return service.set_package_term(db, who, package_id, body)
