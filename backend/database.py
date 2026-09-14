import os

from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

#: Entwicklung: ``housing.db`` im Arbeitsverzeichnis. Produktion: absoluter Pfad,
#: z. B. ``sqlite:////var/lib/gw-scoring/housing.db`` (vier Schrägstriche).
SQLALCHEMY_DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./housing.db")

#: Wartezeit in Millisekunden, wenn die Datenbank gerade von einem anderen
#: Schreibvorgang (z. B. dem Backup) gesperrt ist.
SQLITE_BUSY_TIMEOUT_MS = 5000

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)


@event.listens_for(engine, "connect")
def _configure_sqlite(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    # WAL: Lesen blockiert Schreiben nicht, und ein Backup kann im laufenden Betrieb entstehen.
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
