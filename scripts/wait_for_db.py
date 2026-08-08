import sys
import time

import psycopg2

sys.path.insert(0, ".")
from app.config import settings  # noqa: E402


def main():
    max_attempts = 30
    for attempt in range(1, max_attempts + 1):
        try:
            conn = psycopg2.connect(
                host=settings.APP_DB_HOST,
                port=settings.APP_DB_PORT,
                dbname=settings.APP_DB_NAME,
                user=settings.APP_DB_USER,
                password=settings.APP_DB_PASSWORD,
                connect_timeout=3,
            )
            conn.close()
            print("Database is ready.")
            return
        except Exception as exc:
            print(f"Waiting for database... ({attempt}/{max_attempts}) {exc}")
            time.sleep(2)
    print("Database never became ready.")
    sys.exit(1)


if __name__ == "__main__":
    main()
