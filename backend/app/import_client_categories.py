"""`python -m app.import_client_categories` — kept so the server's cron and deploy/ansible/import.yml
keep working until they have been moved to `python -m app.jobs import_client_categories`.

Delete this once `ansible-playbook site.yml --tags sync` has run (see the README).
"""

from .jobs.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main(["import_client_categories", *__import__("sys").argv[1:]]))
