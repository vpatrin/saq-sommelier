"""Create or promote the admin user from ADMIN_TELEGRAM_ID. Idempotent.

Standalone script — no backend imports. Reads DB connection from env vars
(same ones used by core/config/settings.py).

Usage:
    make create-admin                  # bare metal (reads .env via Makefile)
    docker compose run --rm backend python scripts/create_admin.py  # Docker
"""

import os
import sys
from urllib.parse import quote_plus

from sqlalchemy import create_engine, text


def _database_url() -> str:
    user = os.environ["DB_USER"]
    password = quote_plus(os.environ["DB_PASSWORD"])
    host = os.environ.get("DB_HOST", "localhost")
    port = os.environ.get("DB_PORT", "5432")
    name = os.environ["DB_NAME"]
    return f"postgresql://{user}:{password}@{host}:{port}/{name}"


def main() -> None:
    raw = os.environ.get("ADMIN_TELEGRAM_ID", "").strip()
    if not raw:
        print("ADMIN_TELEGRAM_ID is not set — skipping admin bootstrap.")
        sys.exit(1)

    telegram_id = int(raw)
    engine = create_engine(_database_url())

    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT id, role, is_active FROM users WHERE telegram_id = :tid"),
            {"tid": telegram_id},
        ).fetchone()

        if row:
            user_id, role, is_active = row
            if role == "admin" and is_active:
                print(f"Admin already exists: telegram_id={telegram_id}, id={user_id}")
                return
            conn.execute(
                text("UPDATE users SET role = 'admin', is_active = true WHERE id = :id"),
                {"id": user_id},
            )
            print(f"Promoted existing user to admin: telegram_id={telegram_id}, id={user_id}")
        else:
            conn.execute(
                text(
                    "INSERT INTO users (telegram_id, email, role, is_active, created_at)"
                    " VALUES (:tid, :email, 'admin', true, now())"
                ),
                {"tid": telegram_id, "email": f"admin+{telegram_id}@placeholder.invalid"},
            )
            print(f"Created admin user: telegram_id={telegram_id}")


if __name__ == "__main__":
    main()
