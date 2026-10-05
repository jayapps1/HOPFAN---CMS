# HOPFAN Church Management System

Existing Windows desktop application using CustomTkinter, PostgreSQL, SQLAlchemy and Alembic. The entry point is `hopfan.py`.

Use the existing `.env` for this installation. `.env.example` documents the required keys. Preserve `APP_ENCRYPTION_KEY` when using existing encrypted authenticator secrets.

From `D:\HOPFAN`, using the existing virtual environment:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic check
.\.venv\Scripts\python.exe -m unittest tests.test_attendance tests.test_session -v
.\.venv\Scripts\python.exe -m unittest tests.test_ui_smoke -v
.\.venv\Scripts\python.exe hopfan.py
```

Desktop smoke tests open temporary windows and use synthetic services. PostgreSQL tests create an isolated schema, roll back normal fixtures and remove their generated schema after completion. They require schema-creation permission in the configured database.

Attendance supports dated services and meetings, stable rosters, scoped officers, audited corrections and Draft/Open/Closed/Locked states. An administrator can assign existing users through **Attendance → Manage access**. Select a ministry, choose the grants and explicitly assign the Ministry Attendance Leader role when needed.

The General Overseer role is seeded with attendance viewing and reporting permissions. Additional mutation rights require explicit role permission grants. Central Sunday closure, closed-session corrections and locked-session reopening use separate permissions.

See [the implementation and validation report](docs/attendance_upgrade_report.md) for schema changes, permissions, policy defaults and verification evidence.

Credentials, member photos, local preferences, backups, logs and virtual environments remain local and are excluded from Git.
