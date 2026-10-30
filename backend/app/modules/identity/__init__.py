"""Who may sign in, who they are, and what they may open.

Logging in, the two-step codes, the password links, the account page, and the users and roles
screens. Importing this registers the loader `core.security` asks for the user a token names,
which is what lets every other module say `require("…")` without importing identity.
"""

from ...core.security import set_user_loader
from ..audit import set_user_lister
from . import mfa, repo
from .models import Role, User
from .passwords import create_password_link, user_for_password_token
from .router import router
from .snapshots import role_snapshot, user_snapshot

set_user_loader(repo.active_by_id)
# audit sits below identity, so identity hands it the user list its filter offers
set_user_lister(repo.listed_users)

# User is the one model other modules may name (final_plan.md §4)
__all__ = ["Role", "User", "create_password_link", "mfa", "repo", "role_snapshot", "router",
           "user_for_password_token", "user_snapshot"]
