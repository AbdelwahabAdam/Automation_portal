"""`python -m app.fake_daftra` — kept so the server's cron and deploy/ansible/import.yml
keep working until they have been moved to `python -m app.jobs fake_daftra`.

Delete this once `ansible-playbook site.yml --tags sync` has run (see the README).
"""

from .jobs.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main(["fake_daftra", *__import__("sys").argv[1:]]))
