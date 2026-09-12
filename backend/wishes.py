# -*- coding: utf-8 -*-
"""Wohnungswünsche einer Bewerbung: Parsen, Anzeigen, Abgleichen.

Ein Wunsch ist **kein Freitext**, sondern eine Wohnungskategorie —
Zimmerzahl x Förderungsart, dazu optional die Wohnungsart. Das ist genau der
Schlüssel, den :func:`services.apartment_categories` aus den Wohnungsstammdaten
ableitet; im Frontend wird der Wunsch deshalb aus einer Auswahlliste gewählt
statt getippt.

Dieses Modul hängt bewusst nur an der Standardbibliothek: es wird sowohl vom
Import (:mod:`application_import_service`), vom Fragebogen-Import
(:mod:`import_service`), vom Ranking (:mod:`services`) als auch von der
Startmigration in :mod:`main` benutzt.

Schreibweisen der gepflegten Liste, die der Parser auflöst::

    "2,5 A"      -> Zimmerzahl 2, WBS A
    "3,5 frei"   -> Zimmerzahl 3, freifinanziert
    "1,5 WBS B"  -> Zimmerzahl 1, WBS B
    "B"          -> Förderungsart WBS B, Größe egal
    "Cluster B"  -> Clusterwohnung, WBS B
    "Joker"      -> Joker-Zimmer
    "4 Zimmer"   -> Zimmerzahl 4 (Schreibweise des Haushaltsbogens)

Das halbe Zimmer entfällt wie überall im Modell (``3,5`` -> ``size_rooms = 3``);
die Anzeige nutzt weiterhin die Schreibweise der Liste (:func:`wish_label`).
Ausbau- und Atelierwohnungen zählen laut Vergabepraxis als Standardwohnungen
und erzeugen deshalb keine eigene Wohnungsart im Wunsch.
"""

import json
import re

FUNDING_FREE = "freifinanziert"
FUNDING_A = "WBS A"
FUNDING_B = "WBS B"

CATEGORY_CLUSTER = "Clusterwohnung"
CATEGORY_JOKER = "Joker"
CATEGORY_STANDARD = "Standard Wohnungstypen"

#: Begriffe, die eine Standardwohnung meinen. Sie tragen keine eigene
#: Information: "1,5 B Ausbau / Atelier" ist ein Wunsch, keine drei.
#: Die Liste kürzt diese Begriffe ab ("Ausb / Atelier", "1,5 att", "3,5 kl WBS B").
#: "klein" beschreibt eine Bauvariante derselben Kategorie und ist im Modell
#: ebenfalls keine eigene Angabe.
_STANDARD_WORDS = re.compile(
    r"\b(ausbau|ausbauwohnung|ausb|atelier|atelierwohnung|att|standard|standardwohnung|"
    r"klein|kl|wohnung|wohnungen|zimmer|zi)\b"
)
_CLUSTER_WORDS = re.compile(
    r"\b(cluster|gartencluster|clusterwohnung|c-riegel|wpg|wohngemeinschaft|wg)\b"
)
_JOKER_WORDS = re.compile(r"\bjoker\b")
_FREE_WORDS = re.compile(r"\b(frei|freifinanziert|freifin|ohne\s*wbs|kein\s*wbs)\b")
_WBS_LETTER = re.compile(r"\b(?:wbs\s*)?([ab])\b")
_SIZE = re.compile(r"\b(\d)(?:\.5)?\b")
#: Wohnungsnummern wie "W.204" oder "P.108.1" kommen in der Liste als Hinweis
#: vor ("2,5 A - W.006"); sie sind nicht Teil des Wunsches.
_UNIT_NUMBER = re.compile(r"\b[a-z]\.\d{3}(?:\.\d)?\b")
_DECIMAL = re.compile(r"(\d)\s*[,]\s*(\d)")


def _blank(value) -> bool:
    return value is None or not str(value).strip()


def parse_wish(raw) -> tuple[list[dict], list[str]]:
    """Zerlegt eine Wunsch-Zelle in strukturierte Wünsche.

    Liefert ``(wünsche, nicht_erkannt)``. Teilstücke, aus denen sich **gar
    nichts** ableiten lässt, landen nicht stillschweigend als Freitext in den
    Daten, sondern in ``nicht_erkannt`` — der Import-Assistent zeigt sie zur
    Klärung an.
    """
    if _blank(raw):
        return [], []

    text = str(raw).replace(" ", " ")
    # Dezimalkomma zuerst vereinheitlichen, sonst zerschneidet die Trennung "1,5"
    text = _DECIMAL.sub(r"\1.\2", text)

    wishes: list[dict] = []
    unparsed: list[str] = []
    last_size = None
    for raw_segment in re.split(r"[\n;,/|]+", text):
        raw_segment = raw_segment.strip()
        if not raw_segment:
            continue
        # Wohnungsnummern erst je Teilstück entfernen: "2,5 A - W.006" ist ein
        # Wunsch mit beigefügtem Hinweis, ein Teilstück, das **nur** aus einer
        # Wohnungsnummer besteht ("W.213"), ist dagegen ein Wunsch, den das
        # Modell nicht kennt -- er darf nicht stillschweigend verschwinden.
        segment = _UNIT_NUMBER.sub(" ", raw_segment.lower()).strip()
        wish = _parse_segment(segment) if segment else None
        if wish is None:
            cleaned = (segment or raw_segment).strip(" .-–—?!*()")
            # Reine Füllwörter ("Atelier", "Zimmer") tragen keine eigene
            # Information und sind kein Fehler.
            if cleaned and not _STANDARD_WORDS.fullmatch(cleaned):
                unparsed.append(cleaned)
            continue
        # "3,5 A/B" meint zweimal 3,5 Zimmer: eine reine Förderangabe erbt die
        # zuletzt genannte Zimmerzahl derselben Zelle.
        if (wish["size_rooms"] is None and wish["apartment_category"] is None
                and wish["funding_type"] and last_size is not None):
            wish["size_rooms"] = last_size
        if wish["size_rooms"] is not None:
            last_size = wish["size_rooms"]
        wishes.append(wish)
    return normalize_wishes(wishes), unparsed


def _parse_segment(segment: str) -> dict | None:
    """Ein einzelnes Teilstück -> Wunsch, oder ``None`` wenn nichts erkennbar ist."""
    category = None
    if _JOKER_WORDS.search(segment):
        category = CATEGORY_JOKER
    elif _CLUSTER_WORDS.search(segment):
        category = CATEGORY_CLUSTER

    funding = None
    if _FREE_WORDS.search(segment):
        funding = FUNDING_FREE
    else:
        match = _WBS_LETTER.search(segment)
        if match:
            funding = FUNDING_A if match.group(1) == "a" else FUNDING_B

    size_match = _SIZE.search(segment)
    size = int(size_match.group(1)) if size_match else None

    if category is None and funding is None and size is None:
        return None
    return {"size_rooms": size, "funding_type": funding, "apartment_category": category}


def normalize_wishes(wishes) -> list[dict]:
    """Bringt eine Wunschliste auf die kanonische Form und entfernt Dubletten."""
    result: list[dict] = []
    seen: set[tuple] = set()
    for wish in wishes or []:
        if not isinstance(wish, dict):
            wish = {
                "size_rooms": getattr(wish, "size_rooms", None),
                "funding_type": getattr(wish, "funding_type", None),
                "apartment_category": getattr(wish, "apartment_category", None),
            }
        size = wish.get("size_rooms")
        funding = wish.get("funding_type") or None
        category = wish.get("apartment_category") or None
        if category == CATEGORY_STANDARD:
            # Standard ist der Normalfall und wird nicht gespeichert
            category = None
        entry = {
            "size_rooms": int(size) if size is not None else None,
            "funding_type": funding,
            "apartment_category": category,
        }
        key = (entry["size_rooms"], entry["funding_type"], entry["apartment_category"])
        if key in seen:
            continue
        seen.add(key)
        result.append(entry)
    return result


def category_for_wish(name) -> str | None:
    """Wohnungsart aus dem Fragebogen -> Wunsch-Wohnungsart.

    Ausbau- und Atelierwohnungen zählen als Standardwohnungen und erzeugen
    deshalb keine eigene Angabe (``None``).
    """
    if _blank(name):
        return None
    text = str(name).strip().lower()
    if _JOKER_WORDS.search(text):
        return CATEGORY_JOKER
    if _CLUSTER_WORDS.search(text):
        return CATEGORY_CLUSTER
    return None


def from_household_fields(size_raw, type_raw) -> list[dict]:
    """Wohnungswunsch aus den alten Haushaltsfeldern des Fragebogens.

    ``size_raw`` ist der Freitext der Spalte "Gewünschte Wohnungsgröße",
    ``type_raw`` die Wohnungsart (Liste oder JSON-Text). Jede Größe wird mit
    jeder Wohnungsart kombiniert; fehlt eine Seite, bleibt sie offen ("egal").
    """
    sizes, _ = parse_wish(size_raw)

    raw_types = type_raw
    if isinstance(raw_types, str):
        try:
            parsed = json.loads(raw_types)
        except (ValueError, TypeError):
            parsed = [raw_types]
        raw_types = parsed if isinstance(parsed, list) else [parsed]
    categories = [category_for_wish(t) for t in (raw_types or [])]
    categories = list(dict.fromkeys(categories))

    if not sizes and not categories:
        return []
    if not sizes:
        return normalize_wishes(
            [{"size_rooms": None, "funding_type": None, "apartment_category": c}
             for c in categories]
        )
    if not categories:
        return normalize_wishes(sizes)
    return normalize_wishes([
        {**size, "apartment_category": size.get("apartment_category") or category}
        for size in sizes
        for category in categories
    ])


def size_label(size_rooms) -> str:
    """Zimmerzahl in der Schreibweise der Bauplanung: ``2`` -> ``"2,5"``."""
    if size_rooms is None:
        return "ohne Zimmerangabe"
    if size_rooms <= 0:
        return "ohne Zimmerangabe"
    return f"{int(size_rooms)},5"


def funding_short(funding_type) -> str:
    """Kurzform der Förderungsart wie in der gepflegten Liste."""
    if funding_type == FUNDING_A:
        return "A"
    if funding_type == FUNDING_B:
        return "B"
    if funding_type == FUNDING_FREE:
        return "frei"
    return ""


def wish_label(wish) -> str:
    """Anzeige eines Wunsches in der Schreibweise der Liste, z. B. ``"2,5 A"``."""
    if not isinstance(wish, dict):
        wish = {
            "size_rooms": getattr(wish, "size_rooms", None),
            "funding_type": getattr(wish, "funding_type", None),
            "apartment_category": getattr(wish, "apartment_category", None),
        }
    category = wish.get("apartment_category")
    parts = []
    if wish.get("size_rooms") is not None:
        parts.append(size_label(wish["size_rooms"]))
    if category:
        parts.append(category if category != CATEGORY_CLUSTER else "Cluster")
    short = funding_short(wish.get("funding_type"))
    if short:
        parts.append(short)
    return " ".join(parts) if parts else "beliebig"


def wish_matches(wish, size_rooms, funding_type, apartment_category) -> bool:
    """Passt der Wunsch auf diese Wohnungskategorie? ``None`` im Wunsch heißt "egal"."""
    if not isinstance(wish, dict):
        return False
    if wish.get("size_rooms") is not None and wish["size_rooms"] != size_rooms:
        return False
    if wish.get("funding_type") and wish["funding_type"] != funding_type:
        return False
    wanted = wish.get("apartment_category")
    if wanted:
        return wanted == apartment_category
    # Ohne Angabe der Wohnungsart ist eine Standardwohnung gemeint -- Cluster
    # und Joker werden nicht per Scoring vergeben und müssen ausdrücklich
    # gewünscht werden.
    return apartment_category not in (CATEGORY_CLUSTER, CATEGORY_JOKER)
