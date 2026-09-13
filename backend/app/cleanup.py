from app.core.config import get_settings
from app.db.database import Base, SessionLocal, engine
from app.services.jobs import JobService


def main() -> None:
    if get_settings().storage_bucket:
        print("Cloud Storage lifecycle manages expired job deletion.")
        return
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        count = JobService(session, get_settings()).cleanup_expired()
    print(f"Deleted {count} expired job(s).")


if __name__ == "__main__":
    main()
