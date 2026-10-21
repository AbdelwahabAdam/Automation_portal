"""Create a user or update an existing one from the command line.

Meant for the first admin; after that, users and their roles are managed in the portal.

Usage: python -m app.create_user <username> <password> [--admin] [--name "Full Name"] [--email you@example.com]
"""

import argparse

from sqlalchemy import select

from .admin import EMAIL_RE, USERNAME_RE
from .database import SessionLocal, run_migrations
from .models import User
from .security import hash_password


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("username")
    parser.add_argument("password")
    parser.add_argument("--admin", action="store_true", help="open every page, including the admin pages")
    parser.add_argument("--name", default="")
    parser.add_argument("--email", default="", help="also used to log in and to receive notifications")
    args = parser.parse_args()
    username = args.username.strip().lower()
    email = args.email.strip().lower()
    # The same rules as the users page: a name with "@" would be taken for an email at login
    if not USERNAME_RE.match(username):
        parser.error("the username is 3 to 50 lowercase letters, digits, dots, dashes or underscores")
    if email and not EMAIL_RE.match(email):
        parser.error(f"not an email address: {email}")
    if not 8 <= len(args.password.encode()) <= 72:
        parser.error("the password is 8 to 72 bytes long")

    run_migrations()
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == username))
        action = "Updated" if user else "Created"
        if user is None:
            user = User(username=username)
            db.add(user)
        user.password_hash = hash_password(args.password)
        user.is_admin = bool(user.is_admin) or args.admin
        user.is_active = True
        user.full_name = args.name or user.full_name or username
        user.email = email or user.email
        db.commit()
    print(f"{action} user '{username}'" + (" as admin" if user.is_admin else ""))


if __name__ == "__main__":
    main()
