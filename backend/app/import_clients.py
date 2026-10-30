"""`python -m app.import_clients` — kept so the server's cron and deploy/ansible/import.yml
keep working until they have been moved to `python -m app.jobs sync_clients`.

Delete this once `ansible-playbook site.yml --tags sync` has run (see the README).
"""

from .jobs.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main(["sync_clients", *__import__("sys").argv[1:]]))
