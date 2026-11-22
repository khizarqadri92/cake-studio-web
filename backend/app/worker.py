"""Background worker: python -m app.worker"""
import logging
import time

from app.db.session import session_factory
from app.services import notify

log = logging.getLogger("worker")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    senders = notify.configured_senders()
    log.info("worker started; providers: %s", ", ".join(senders) or "none")
    while True:
        try:
            db = session_factory()
            try:
                if notify.process_pending(db, senders):
                    log.info("processed notifications")
            finally:
                db.close()
        except Exception:
            log.exception("worker iteration failed")
        time.sleep(10)


if __name__ == "__main__":
    main()
