"""Copy Daftra's client categories (التصنيف) into our database, with each one's الإمارة and المنطقة.

Usage: python -m app.import_client_categories

The forms read the categories from our table, never from Daftra. The portal runs this by itself the
first time it starts with an empty table; run it again by hand when categories were added or renamed
in Daftra. It reads every client to work out where each category's clients live, so it takes minutes.
Categories are matched by Daftra's id: existing rows are updated, new ones added, none removed
(a request may still point at one).
"""

from sqlalchemy import select

from . import daftra
from .database import SessionLocal, run_migrations
from .models import ClientCategory


def import_categories() -> tuple[int, int]:
    """Returns (added, updated)."""
    rows = daftra.client_categories_with_location()
    added = updated = 0
    with SessionLocal() as db:
        existing = {category.id: category for category in db.scalars(select(ClientCategory))}
        for row in rows:
            category = existing.get(row["id"])
            if category is None:
                db.add(ClientCategory(id=row["id"], name=row["name"], emirate=row["emirate"], area=row["area"]))
                added += 1
            elif (category.name, category.emirate, category.area) != (row["name"], row["emirate"], row["area"]):
                category.name, category.emirate, category.area = row["name"], row["emirate"], row["area"]
                updated += 1
        db.commit()
    return added, updated


def main():
    run_migrations()
    added, updated = import_categories()
    print(f"Client categories: {added} added, {updated} updated")


if __name__ == "__main__":
    main()
