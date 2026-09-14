import pandas as pd
from sqlalchemy.orm import Session, selectinload
from . import models, apartment_seed_data, scoring, wishes as wishes_mod
from datetime import datetime, date
from typing import NamedTuple
import io
import re

def process_excel_upload(file_contents: bytes, db: Session):
    # Read Excel file
    # Assuming a flat structure where each row is a person, grouped by "Household Name"
    df = pd.read_excel(io.BytesIO(file_contents))
    
    # Expected columns:
    # Household Name, Member Since, Engagement Score, 
    # First Name, Last Name, Birth Date, Gender, Occupation, Education, Cultural Background, Special Needs
    
    # Group by Household Name to create households first
    grouped = df.groupby("Household Name")
    
    created_count = 0
    
    for household_name, group in grouped:
        # Take household data from the first row of the group
        first_row = group.iloc[0]
        
        # Parse dates and scores
        member_since = pd.to_datetime(first_row.get("Member Since"), errors='coerce')
        if pd.isna(member_since):
            member_since = None

        engagement_score = float(first_row.get("Engagement Score", 0.0))

        db_household = models.Household(
            name=str(household_name),
            engagement_score=engagement_score
        )
        db.add(db_household)
        db.flush()

        for index, row in group.iterrows():
            birth_date = pd.to_datetime(row.get("Birth Date"), errors='coerce')
            row_member_since = pd.to_datetime(row.get("Member Since"), errors='coerce')
            if pd.isna(row_member_since):
                row_member_since = member_since

            db_person = models.Person(
                household_id=db_household.id,
                first_name=str(row.get("First Name", "")),
                last_name=str(row.get("Last Name", "")),
                birth_date=birth_date,
                gender=str(row.get("Gender", "")),
                occupation_type=str(row.get("Occupation", "")),
                education_level=str(row.get("Education", "")),
                cultural_background=str(row.get("Cultural Background", "")),
                special_needs=str(row.get("Special Needs", "")).strip() or None,
                member_since=row_member_since,
            )
            db.add(db_person)
        
        created_count += 1
        
    db.commit()
    return {"message": f"Erfolgreich {created_count} Haushalte und {len(df)} Personen importiert."}


def seed_apartments(db: Session) -> int:
    """Legt die Wohnungsstammdaten an (siehe ``apartment_seed_data``).

    Idempotent: Wohnungen, deren ``unit_number`` bereits existiert, bleiben
    unverändert — im Frontend vorgenommene Änderungen werden nicht überschrieben.
    """
    existing = {row[0] for row in db.query(models.Apartment.unit_number).all()}
    created = 0
    for row in apartment_seed_data.APARTMENTS:
        data = dict(zip(apartment_seed_data.FIELDS, row))
        if data["unit_number"] in existing:
            continue
        db.add(models.Apartment(**data))
        created += 1
    if created:
        db.commit()
    return created


def assign_household(db: Session, apartment: models.Apartment, household_id: int | None) -> bool:
    """Ordnet der Wohnung den Haushalt zu, der darin wohnt (oder löst die Zuordnung).

    Ein Haushalt wohnt in genau einer Wohnung: eine bestehende Zuordnung des
    Haushalts zu einer anderen Wohnung wird dabei gelöst. Der Haushalt gilt
    danach als Bewohner (``is_resident``).
    """
    if household_id is None:
        if apartment.household_id is None:
            return False
        old_hh = db.query(models.Household).filter(
            models.Household.id == apartment.household_id
        ).first()
        apartment.household_id = None
        if old_hh:
            old_hh.is_resident = False
            old_hh.updated_at = datetime.utcnow()
        return True

    household = db.query(models.Household).filter(models.Household.id == household_id).first()
    if not household:
        raise ValueError(f"Haushalt {household_id} nicht gefunden")

    if apartment.household_id == household_id:
        return False

    for other in db.query(models.Apartment).filter(
        models.Apartment.household_id == household_id,
        models.Apartment.id != apartment.id,
    ).all():
        other.household_id = None

    apartment.household_id = household_id
    household.is_resident = True
    if not household.apartment_unit:
        household.apartment_unit = apartment.unit_number
    household.updated_at = datetime.utcnow()
    close_open_applications(db, household_id, apartment)
    return True


# --- Bewerbungen -------------------------------------------------------------

def open_applications(
    db: Session,
    household_id: int | None = None,
    kind: str | None = None,
) -> list[models.Application]:
    """Offene, nicht archivierte Bewerbungen."""
    query = db.query(models.Application).filter(
        models.Application.status == "offen",
        models.Application.archived == False,
    )
    if household_id is not None:
        query = query.filter(models.Application.household_id == household_id)
    if kind is not None:
        query = query.filter(models.Application.kind == kind)
    return query.all()


def close_open_applications(
    db: Session,
    household_id: int,
    apartment: models.Apartment,
) -> int:
    """Schließt beim Einzug alle offenen Bewerbungen des Haushalts ab.

    Damit entsteht die Spalte "neue Wohnung" der gepflegten Liste von selbst:
    Status und Wohnung werden nicht getippt, sondern aus der Zuordnung
    abgeleitet. Wird die Zuordnung später wieder gelöst, bleibt die erfüllte
    Bewerbung als Historie bestehen.
    """
    now = datetime.utcnow()
    closed = 0
    for application in open_applications(db, household_id=household_id):
        application.status = "erfuellt"
        application.fulfilled_apartment_id = apartment.id
        application.fulfilled_at = now
        application.updated_at = now
        closed += 1
    return closed


def application_wishes(application: models.Application) -> list[dict]:
    """Die Wünsche einer Bewerbung in kanonischer Form."""
    return wishes_mod.normalize_wishes(application.wishes or [])


def wishes_match_category(
    application: models.Application,
    size_rooms: int | None,
    funding_type: str | None,
    apartment_category: str | None = None,
) -> bool:
    """Wünscht sich die Bewerbung diese Wohnungskategorie ausdrücklich?"""
    return any(
        wishes_mod.wish_matches(wish, size_rooms, funding_type, apartment_category)
        for wish in application_wishes(application)
    )


# --- Eignung Haushalt <-> Wohnung ---------------------------------------

#: Wohnungsarten, die **nicht** per Scoring vergeben werden. Clusterwohnungen
#: und Joker-Zimmer werden auf anderem Weg belegt; sie bilden deshalb keine
#: Wohnungskategorie und tauchen in der Rangliste nicht auf.
NON_SCORED_CATEGORIES = frozenset({"Clusterwohnung", "Joker"})


def is_scored_category(apartment_category: str | None) -> bool:
    """Wird diese Wohnungsart per Scoring vergeben?

    Clusterwohnungen und Joker-Zimmer nicht (siehe
    :data:`NON_SCORED_CATEGORIES`); alle anderen — auch Wohnungen ohne
    gepflegte Wohnungsart — schon.
    """
    return (apartment_category or "").strip() not in NON_SCORED_CATEGORIES


# Förderstufen: ein Haushalt darf jede Wohnung bewohnen, deren Stufe
# höchstens seiner eigenen entspricht (A > B > freifinanziert).
_FUNDING_ORDER = {None: 0, "B": 1, "A": 2}


def wbs_level(value: str | None) -> str | None:
    """Normalisiert Förderungsart bzw. WBS-Status auf ``"A"``, ``"B"`` oder ``None``.

    Erkennt sowohl die Wohnungswerte (``"WBS A"``, ``"freifinanziert"``) als auch
    die Haushaltswerte aus dem Import (``"WBS Einkommensgruppe A"``, ``"kein WBS"``).
    ``None`` steht für „freifinanziert / ohne Angabe".
    """
    if not value:
        return None
    text = str(value).strip().upper()
    if "WBS" not in text or "KEIN" in text:
        return None
    match = re.search(r"\b([AB])\b", text)
    return match.group(1) if match else None


def funding_matches(household_wbs: str | None, apartment_funding: str | None) -> bool:
    """WBS A darf A/B/freifinanziert, WBS B darf B/freifinanziert, sonst nur freifinanziert."""
    return (_FUNDING_ORDER[wbs_level(household_wbs)]
            >= _FUNDING_ORDER[wbs_level(apartment_funding)])


def member_count(household: models.Household) -> int:
    """Anzahl der nicht archivierten Personen im Haushalt."""
    return sum(1 for p in household.people if not p.archived)


def is_eligible(
    members: int,
    household_wbs: str | None,
    size_rooms: int | None,
    min_occupants: int | None,
    funding_type: str | None,
) -> bool:
    """Kommt ein Haushalt dieser Größe für eine solche Wohnung in Frage?

    - Der Haushalt muss die Mindestanzahl an Bewohnern der Wohnung erfüllen.
    - Die Wohnung darf nicht weniger Zimmer haben als der Haushalt Mitglieder.
      Jede Wohnungsart kann eine Zimmerzahl haben; nur Wohnungen ohne
      Zimmerangabe unterliegen dieser Schranke nicht.
    - Die Förderbedingung muss erfüllt sein (siehe ``funding_matches``).
    """
    if members < (min_occupants or 0):
        return False
    if size_rooms is not None and size_rooms < members:
        return False
    return funding_matches(household_wbs, funding_type)


def apartment_categories(db: Session) -> dict[tuple[int | None, str], int]:
    """Alle per Scoring vergebenen Wohnungskategorien (Zimmerzahl,
    Förderungsart) mit ihrer niedrigsten Mindestbewohnerzahl.

    Clusterwohnungen und Joker-Zimmer bleiben außen vor (siehe
    :func:`is_scored_category`).
    """
    categories: dict[tuple[int | None, str], int] = {}
    for size_rooms, funding_type, min_occupants, category in db.query(
        models.Apartment.size_rooms,
        models.Apartment.funding_type,
        models.Apartment.min_occupants,
        models.Apartment.apartment_category,
    ).all():
        if not is_scored_category(category):
            continue
        key = (size_rooms, funding_type)
        required = min_occupants or 0
        if key not in categories or required < categories[key]:
            categories[key] = required
    return categories


def apartment_category_options(db: Session) -> list[dict]:
    """Wählbare Wunschkategorien, abgeleitet aus den Wohnungsstammdaten.

    Das ist die Auswahlliste der Bewerbungspflege: Sie entsteht aus den
    tatsächlich vorhandenen Wohnungen und kann deshalb nicht von den
    Stammdaten abweichen — anders als eine getippte Angabe. Ausbau- und
    Atelierwohnungen laufen als Standardwohnungen mit; Clusterwohnungen und
    Joker-Zimmer behalten ihre Wohnungsart, weil sie ausdrücklich gewünscht
    werden müssen.
    """
    counts: dict[tuple, int] = {}
    for size_rooms, funding_type, category in db.query(
        models.Apartment.size_rooms,
        models.Apartment.funding_type,
        models.Apartment.apartment_category,
    ).all():
        key_category = (category or "").strip()
        if key_category not in NON_SCORED_CATEGORIES:
            key_category = None
        key = (size_rooms, funding_type, key_category)
        counts[key] = counts.get(key, 0) + 1

    def sort_key(key: tuple) -> tuple:
        size_rooms, funding_type, category = key
        return (
            0 if category is None else (1 if category == wishes_mod.CATEGORY_CLUSTER else 2),
            size_rooms is None,
            size_rooms or 0,
            funding_type or "",
        )

    options = []
    for key in sorted(counts, key=sort_key):
        size_rooms, funding_type, category = key
        options.append({
            "size_rooms": size_rooms,
            "funding_type": funding_type,
            "apartment_category": category,
            "label": wishes_mod.wish_label({
                "size_rooms": size_rooms,
                "funding_type": funding_type,
                "apartment_category": category,
            }),
            "apartment_count": counts[key],
        })

    # Die gepflegte Liste notiert Cluster und Joker oft ohne Zimmerzahl
    # ("Cluster", "Cluster B", "Joker"). Diese Sammel-Wünsche gehören deshalb
    # ebenfalls in die Auswahl.
    for category in (wishes_mod.CATEGORY_CLUSTER, wishes_mod.CATEGORY_JOKER):
        keys = [k for k in counts if k[2] == category]
        # Gibt es die Art nur in einer Ausprägung, wäre der Sammel-Wunsch ein Duplikat.
        if len(keys) < 2:
            continue
        total = sum(counts[k] for k in keys)
        options.append({
            "size_rooms": None,
            "funding_type": None,
            "apartment_category": category,
            "label": wishes_mod.wish_label({
                "size_rooms": None, "funding_type": None, "apartment_category": category,
            }),
            "apartment_count": total,
        })
    return options


class RankedEntry(NamedTuple):
    """Ein Haushalt in einer Wohnungskategorie samt der dort erreichten Punkte."""

    household: models.Household
    members: int
    base_score: float        # haushaltseigene Kriterien (``Household.total_score``)
    occupancy_score: float   # gewichtete Wohnraumausnutzung dieser Zimmerzahl
    total_score: float       # base_score + occupancy_score
    application: models.Application
    by_wish_only: bool       # nur über den ausdrücklichen Wunsch in dieser Kategorie
    is_stale: bool = False   # gespeicherte Grundpunktzahl weicht von der aktuellen Berechnung ab


class PriorityEntry(NamedTuple):
    """Ein Wechselwunsch in einer Wohnungskategorie -- Vorrang nach Datum."""

    household: models.Household
    members: int
    application: models.Application


def _requested_sort_key(application: models.Application):
    """Älterer Wunsch zuerst; Bewerbungen ohne Datum ans Ende."""
    return (application.requested_at is None, application.requested_at or datetime.max)


def open_applications_with_households(db: Session, kind: str) -> list[models.Application]:
    """Offene Bewerbungen einer Art samt Haushalt und Personen, ohne archivierte."""
    return [
        application
        for application in (
            db.query(models.Application)
            .options(
                selectinload(models.Application.household)
                .selectinload(models.Household.people)
            )
            .filter(models.Application.status == "offen")
            .filter(models.Application.archived == False)
            .filter(models.Application.kind == kind)
            .all()
        )
        if application.household is not None and not application.household.archived
    ]


def build_ranking(db: Session) -> list[dict]:
    """Rangliste je Wohnungskategorie (Zimmerzahl x Förderungsart).

    Bezugsmenge sind die Haushalte mit **offener Bewerbung**; ohne Bewerbung
    steht ein Haushalt in keiner Kategorie.

    Je Kategorie entstehen zwei Blöcke:

    **Vorrang** — offene Bewerbungen der Art ``wechselwunsch``. Das sind
    bestehende Bewohner-Haushalte; sie werden vorrangig berücksichtigt und
    nach dem Zeitpunkt des Wunsches (``requested_at``) gereiht, nicht per
    Scoring. Sie erscheinen **nur** in den ausdrücklich gewünschten
    Kategorien.

    **Rangliste** — offene Bewerbungen der Art ``wartepool``: Haushalte, die
    noch nicht im Projekt wohnen. Sie erscheinen in jeder Kategorie, für die
    sie in Frage kommen (``is_eligible``; innerhalb einer Kategorie genügt
    eine passende Wohnung, deshalb zählt die niedrigste Mindestbewohnerzahl)
    **und** zusätzlich in jeder Kategorie, die sie ausdrücklich wünschen.
    Letztere tragen ``by_wish_only``: die Eignungsprüfung würde sie
    ausschließen, aber die Angaben zum Haushalt (z. B. die Mitgliederzahl)
    sind möglicherweise unvollständig — die Entscheidung bleibt bei der
    Belegungskommission.

    Clusterwohnungen und Joker-Zimmer werden nicht per Scoring vergeben und
    bilden deshalb keine Kategorie (siehe ``apartment_categories``); Joker
    läuft als eigene Warteliste (``build_joker_waitlist``).

    Der Score ist **nicht** pauschal: zur Grundpunktzahl aus
    ``scoring.run_scoring`` kommt je Kategorie die Wohnraumausnutzung hinzu
    (siehe ``scoring.calculate_occupancy_score``). Derselbe Haushalt steht
    in einer Kategorie, die er ausfüllt, deshalb höher als in einer größeren.
    """
    categories = apartment_categories(db)
    config = scoring.get_config_dict(db)

    # Wartepool: Bewohner suchen keine Wohnung und bleiben draußen.
    pool = [
        (application, member_count(application.household))
        for application in open_applications_with_households(db, "wartepool")
        if not application.household.is_resident
    ]
    changes = [
        (application, member_count(application.household))
        for application in open_applications_with_households(db, "wechselwunsch")
    ]
    # Gespeicherte Grundpunktzahl zum Stichtag ihrer Berechnung nachrechnen: weicht
    # sie ab, haben sich die Daten seither geaendert. Je Haushalt einmal, nicht je Kategorie.
    reference_cache: dict = {}
    stale = {
        application.household.id: scoring.explain_as_calculated(
            db, application.household, config, reference_cache)["is_stale"]
        for application, _ in pool
    }

    groups = []
    for (size_rooms, funding_type), min_occupants in sorted(
        categories.items(),
        key=lambda item: (item[0][0] is None, item[0][0] or 0, item[0][1]),
    ):
        priority = [
            PriorityEntry(
                household=application.household,
                members=members,
                application=application,
            )
            for application, members in changes
            if wishes_match_category(application, size_rooms, funding_type)
        ]
        priority.sort(key=lambda e: _requested_sort_key(e.application))

        entries = []
        for application, members in pool:
            household = application.household
            eligible = is_eligible(members, household.wbs_status,
                                   size_rooms, min_occupants, funding_type)
            wished = wishes_match_category(application, size_rooms, funding_type)
            if not eligible and not wished:
                continue
            base = household.total_score or 0.0
            occupancy = scoring.calculate_occupancy_score(members, size_rooms, config)
            entries.append(RankedEntry(
                household=household,
                members=members,
                base_score=base,
                occupancy_score=occupancy,
                total_score=base + occupancy,
                application=application,
                by_wish_only=not eligible,
                is_stale=stale[household.id],
            ))
        entries.sort(key=lambda e: e.total_score, reverse=True)
        groups.append({
            "size_rooms": size_rooms,
            "funding_type": funding_type,
            "priority": priority,
            "households": entries,
        })
    return groups


def build_joker_waitlist(db: Session) -> list[PriorityEntry]:
    """Bewerbungen auf ein Joker-Zimmer, nach dem Zeitpunkt des Wunsches gereiht.

    Joker-Zimmer können nur von bestehenden Haushalten angemietet werden und
    bilden keine Wohnungskategorie. Die Vergabe folgt wie beim Wechselwunsch
    der Reihenfolge, in der der Wunsch geäußert wurde.
    """
    entries = [
        PriorityEntry(
            household=application.household,
            members=member_count(application.household),
            application=application,
        )
        for application in open_applications_with_households(db, "joker")
    ]
    entries.sort(key=lambda e: _requested_sort_key(e.application))
    return entries
