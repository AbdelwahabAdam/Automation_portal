"""`python -m app.import_packages_from_proposals` — kept so the server's cron and deploy/ansible/import.yml
keep working until they have been moved to `python -m app.jobs import_catalog`.

Delete this once `ansible-playbook site.yml --tags sync` has run (see the README).
"""

from .jobs.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main(["import_catalog", *__import__("sys").argv[1:]]))
