"""Startmigration aus der Zeit vor Alembic.

Hebt eine Datenbank, die vor Einführung von Alembic entstanden ist, auf den Stand
der Ausgangsrevision (``backend/migrations/versions/0001_baseline.py``). Danach
wird sie von ``backend.migrate`` auf diese Revision gestempelt und läuft ab dann
ausschließlich über Alembic. Das gilt auch, wenn eine solche Datenbank als
Erstbefüllung in die Produktion übernommen wird.

**Nicht erweitern.** Neue Schema- oder Datenänderungen gehören in eine
Alembic-Revision.
"""
import json as _json
from datetime import datetime

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from . import models, wishes


def upgrade_legacy_sqlite(engine: Engine) -> None:
    models.Base.metadata.create_all(bind=engine)

    with engine.connect() as conn:
        hh_columns = {c["name"] for c in inspect(engine).get_columns("households")}
        hh_migrations = {
            "is_resident": "ALTER TABLE households ADD COLUMN is_resident BOOLEAN DEFAULT 0",
            "wbs_status": "ALTER TABLE households ADD COLUMN wbs_status TEXT",
            "pets_count": "ALTER TABLE households ADD COLUMN pets_count INTEGER DEFAULT 0",
            "pets_info": "ALTER TABLE households ADD COLUMN pets_info TEXT",
            # desired_apartment_size/-type werden nicht mehr angelegt: der Wunsch liegt
            # an der Bewerbung. Bestehende Spalten werden weiter unten migriert und entfernt.
            "wheelchair_accessible": "ALTER TABLE households ADD COLUMN wheelchair_accessible BOOLEAN DEFAULT 0",
            "financial_status": "ALTER TABLE households ADD COLUMN financial_status TEXT",
            "import_source": "ALTER TABLE households ADD COLUMN import_source TEXT",
            "import_timestamp": "ALTER TABLE households ADD COLUMN import_timestamp DATETIME",
            "household_member_count": "ALTER TABLE households ADD COLUMN household_member_count INTEGER",
            "cultural_diversity_score": "ALTER TABLE households ADD COLUMN cultural_diversity_score REAL DEFAULT 0.0",
            "special_needs_score": "ALTER TABLE households ADD COLUMN special_needs_score REAL DEFAULT 0.0",
            "archived": "ALTER TABLE households ADD COLUMN archived BOOLEAN DEFAULT 0",
            "updated_at": "ALTER TABLE households ADD COLUMN updated_at DATETIME",
            "apartment_unit": "ALTER TABLE households ADD COLUMN apartment_unit TEXT",
            "vcf_import_timestamp": "ALTER TABLE households ADD COLUMN vcf_import_timestamp DATETIME",
            "score_calculated_at": "ALTER TABLE households ADD COLUMN score_calculated_at DATETIME",
        }
        for col, sql in hh_migrations.items():
            if col not in hh_columns:
                conn.execute(text(sql))

        person_columns = {c["name"] for c in inspect(engine).get_columns("people")}
        person_migrations = {
            "member_number": "ALTER TABLE people ADD COLUMN member_number TEXT",
            "individual_import_timestamp": "ALTER TABLE people ADD COLUMN individual_import_timestamp DATETIME",
            "archived": "ALTER TABLE people ADD COLUMN archived BOOLEAN DEFAULT 0",
            "updated_at": "ALTER TABLE people ADD COLUMN updated_at DATETIME",
            "member_since": "ALTER TABLE people ADD COLUMN member_since DATETIME",
            "vcf_import_timestamp": "ALTER TABLE people ADD COLUMN vcf_import_timestamp DATETIME",
        }
        for col, sql in person_migrations.items():
            if col not in person_columns:
                conn.execute(text(sql))

        apartment_columns = {c["name"] for c in inspect(engine).get_columns("apartments")}
        apartment_migrations = {
            "area_shares": "ALTER TABLE apartments ADD COLUMN area_shares REAL",
            "area_rent": "ALTER TABLE apartments ADD COLUMN area_rent REAL",
            "area_utilities": "ALTER TABLE apartments ADD COLUMN area_utilities REAL",
            "apartment_category": "ALTER TABLE apartments ADD COLUMN apartment_category TEXT",
            "is_small": "ALTER TABLE apartments ADD COLUMN is_small BOOLEAN DEFAULT 0",
            "min_occupants": "ALTER TABLE apartments ADD COLUMN min_occupants INTEGER",
            "household_id": "ALTER TABLE apartments ADD COLUMN household_id INTEGER REFERENCES households(id)",
        }
        for col, sql in apartment_migrations.items():
            if col not in apartment_columns:
                conn.execute(text(sql))

        # Mini WGs sind Standardwohnungen mit 3 Zimmern, die klein ausfallen.
        # Muss laufen, solange die alte Typ-Spalte sie noch identifizieren kann.
        if "apartment_type" in apartment_columns:
            conn.execute(text(
                "UPDATE apartments SET apartment_category = 'Standard Wohnungstypen',"
                " size_rooms = 3, is_small = 1 WHERE apartment_type = 'Mini WG'"
            ))

        # C-Riegel, Gartencluster und Wohngemeinschaften sind Clusterwohnungen
        conn.execute(text(
            "UPDATE apartments SET apartment_category = 'Clusterwohnung'"
            " WHERE apartment_category IN ('C-Riegel', 'Gartencluster', 'Wohngemeinschaft')"
        ))

        # Halbe Zimmer entfallen: 3.5 -> 3
        conn.execute(text(
            "UPDATE apartments SET size_rooms = CAST(size_rooms AS INTEGER) WHERE size_rooms IS NOT NULL"
        ))

        # Etage und Rohwert "Typ" werden nicht mehr geführt
        for col in ("floor", "apartment_type"):
            if col in apartment_columns:
                conn.execute(text(f"ALTER TABLE apartments DROP COLUMN {col}"))

        # Migrate member_since from households to people
        if "member_since" in hh_columns:
            conn.execute(text(
                "UPDATE people SET member_since = ("
                "  SELECT households.member_since FROM households"
                "  WHERE households.id = people.household_id"
                ") WHERE people.member_since IS NULL"
            ))

        # Migrate special_needs from BOOLEAN to TEXT
        result = conn.execute(text("SELECT typeof(special_needs) FROM people WHERE special_needs IS NOT NULL LIMIT 1"))
        row = result.fetchone()
        if row and row[0] == "integer":
            conn.execute(text("UPDATE people SET special_needs = NULL WHERE special_needs = 0"))
            conn.execute(text("UPDATE people SET special_needs = 'Ja' WHERE special_needs = 1"))

        # Der alte Wohnungswunsch am Haushalt wird nur noch aufbereitet, damit ihn die
        # Übernahme in die Bewerbung (weiter unten) sauber lesen kann. Bei einer neuen
        # Datenbank gibt es die Spalten nicht mehr.
        if "desired_apartment_type" in hh_columns:
            # Migrate desired_apartment_type from plain string to JSON array
            rows = conn.execute(text(
                "SELECT id, desired_apartment_type FROM households "
                "WHERE desired_apartment_type IS NOT NULL AND desired_apartment_type != ''"
            )).fetchall()
            for r in rows:
                val = r[1]
                try:
                    parsed = _json.loads(val)
                    if isinstance(parsed, list):
                        continue
                except (ValueError, TypeError):
                    pass
                arr = _json.dumps([val])
                conn.execute(
                    text("UPDATE households SET desired_apartment_type = :v WHERE id = :id"),
                    {"v": arr, "id": r[0]},
                )

            # "Gartencluster" ist keine eigene Wohnungsart mehr, sondern eine Clusterwohnung
            rows = conn.execute(text(
                "SELECT id, desired_apartment_type FROM households "
                "WHERE desired_apartment_type LIKE '%Gartencluster%'"
            )).fetchall()
            for r in rows:
                try:
                    types = _json.loads(r[1])
                except (ValueError, TypeError):
                    continue
                if not isinstance(types, list):
                    continue
                replaced = ["Clusterwohnung" if t == "Gartencluster" else t for t in types]
                deduped = list(dict.fromkeys(replaced))
                conn.execute(
                    text("UPDATE households SET desired_apartment_type = :v WHERE id = :id"),
                    {"v": _json.dumps(deduped), "id": r[0]},
                )

        # --- Bewerbungen: vom Wohnungs-Link zum eigenständigen Objekt ---
        app_columns = {c["name"] for c in inspect(engine).get_columns("applications")}
        application_migrations = {
            "kind": "ALTER TABLE applications ADD COLUMN kind TEXT DEFAULT 'wartepool'",
            "requested_at": "ALTER TABLE applications ADD COLUMN requested_at DATETIME",
            "wishes": "ALTER TABLE applications ADD COLUMN wishes TEXT",
            "status": "ALTER TABLE applications ADD COLUMN status TEXT DEFAULT 'offen'",
            "status_note": "ALTER TABLE applications ADD COLUMN status_note TEXT",
            "special_case": "ALTER TABLE applications ADD COLUMN special_case BOOLEAN DEFAULT 0",
            "special_case_note": "ALTER TABLE applications ADD COLUMN special_case_note TEXT",
            "note": "ALTER TABLE applications ADD COLUMN note TEXT",
            "fulfilled_apartment_id":
                "ALTER TABLE applications ADD COLUMN fulfilled_apartment_id INTEGER"
                " REFERENCES apartments(id)",
            "fulfilled_at": "ALTER TABLE applications ADD COLUMN fulfilled_at DATETIME",
            "created_at": "ALTER TABLE applications ADD COLUMN created_at DATETIME",
            "updated_at": "ALTER TABLE applications ADD COLUMN updated_at DATETIME",
            "archived": "ALTER TABLE applications ADD COLUMN archived BOOLEAN DEFAULT 0",
        }
        for col, sql in application_migrations.items():
            if col not in app_columns:
                conn.execute(text(sql))

        # Die alte Bewerbung zeigte auf eine konkrete Wohnung -- das ist heute die
        # erfüllte Wohnung. SQLite kann eine Spalte, die in einer Fremdschlüssel-
        # definition steht, nicht entfernen: die Tabelle wird deshalb neu aufgebaut.
        if "apartment_id" in app_columns:
            conn.execute(text(
                "UPDATE applications SET fulfilled_apartment_id = apartment_id"
                " WHERE fulfilled_apartment_id IS NULL AND apartment_id IS NOT NULL"
            ))
            carried = (
                "id, household_id, kind, requested_at, wishes, status, status_note,"
                " special_case, special_case_note, note, fulfilled_apartment_id,"
                " fulfilled_at, created_at, updated_at, archived"
            )
            conn.execute(text("ALTER TABLE applications RENAME TO applications_old"))
            # Indizes wandern beim Umbenennen mit und würden die Namen blockieren.
            for (index_name,) in conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
                " AND tbl_name = 'applications_old' AND name NOT LIKE 'sqlite_autoindex%'"
            )).fetchall():
                conn.execute(text(f'DROP INDEX IF EXISTS "{index_name}"'))
            models.Application.__table__.create(bind=conn)
            conn.execute(text(
                f"INSERT INTO applications ({carried}) SELECT {carried} FROM applications_old"
            ))
            conn.execute(text("DROP TABLE applications_old"))

        # Unbekannte Status ("applied") werden zu "offen".
        conn.execute(text("UPDATE applications SET kind = 'wartepool' WHERE kind IS NULL OR kind = ''"))
        conn.execute(text(
            "UPDATE applications SET status = 'offen'"
            " WHERE status IS NULL OR status NOT IN ('offen', 'erfuellt', 'zurueckgezogen')"
        ))
        conn.execute(text("UPDATE applications SET archived = 0 WHERE archived IS NULL"))
        conn.execute(text("UPDATE applications SET special_case = 0 WHERE special_case IS NULL"))

        # Der Wohnungswunsch wandert vom Haushalt in die Bewerbung. Bewohner-
        # Haushalte erhalten einen Wechselwunsch, alle anderen eine Wartepool-
        # Bewerbung; die Bewerbungsliste aktualisiert sie später mit dem echten Datum.
        if "desired_apartment_size" in hh_columns or "desired_apartment_type" in hh_columns:
            size_col = "desired_apartment_size" if "desired_apartment_size" in hh_columns else "NULL"
            type_col = "desired_apartment_type" if "desired_apartment_type" in hh_columns else "NULL"
            existing = {
                (row[1], row[2]): (row[0], row[3], row[4])       # (Haushalt, Art) -> (id, wishes, seit)
                for row in conn.execute(text(
                    "SELECT id, household_id, kind, wishes, requested_at FROM applications"
                )).fetchall()
            }
            rows = conn.execute(text(
                f"SELECT id, {size_col}, {type_col}, is_resident, import_timestamp, application_date"
                " FROM households"
            )).fetchall()
            for hh_id, size_raw, type_raw, is_resident, imported, applied in rows:
                wish_list = wishes.from_household_fields(size_raw, type_raw)
                if not wish_list:
                    continue
                kind = "wechselwunsch" if is_resident else "wartepool"
                params = {
                    "hh": hh_id,
                    "kind": kind,
                    "req": imported or applied,
                    "wishes": _json.dumps(wish_list, ensure_ascii=False),
                    "now": datetime.utcnow(),
                }
                match = existing.get((hh_id, kind))
                if match is None:
                    conn.execute(text(
                        "INSERT INTO applications (household_id, kind, requested_at, wishes, status,"
                        " special_case, created_at, archived)"
                        " VALUES (:hh, :kind, :req, :wishes, 'offen', 0, :now, 0)"
                    ), params)
                    continue
                # Eine bereits vorhandene Bewerbung wird nicht überschrieben, aber
                # um den Wunsch ergänzt, solange sie noch keinen trägt.
                application_id, old_wishes, old_requested = match
                if old_wishes and old_wishes not in ("null", "[]"):
                    continue
                params["id"] = application_id
                conn.execute(text(
                    "UPDATE applications SET wishes = :wishes,"
                    " requested_at = COALESCE(requested_at, :req) WHERE id = :id"
                ), params)

        for col in ("desired_apartment_size", "desired_apartment_type"):
            if col in hh_columns:
                conn.execute(text(f"ALTER TABLE households DROP COLUMN {col}"))

        conn.commit()
