# Wohnungsstammdaten als ergänzender Seed statt Import

Die 131 Wohnungen der Genossenschaft werden nicht importiert, sondern beim Start aus `backend/apartment_seed_data.py` angelegt (erzeugt aus `imported_data/Wohnungen.xlsx`). Der Seed ist idempotent und ergänzt nur: Wohnungen, deren Nummer schon existiert, bleiben unverändert, damit Änderungen aus dem Frontend nie überschrieben werden. Danach werden die Wohnungen ausschließlich im Frontend gepflegt.

## Consequences

Eine geänderte `Wohnungen.xlsx` wirkt nicht auf bestehende Wohnungen; Korrekturen erfolgen im Tab „Wohnungen“. Außer Wohnungen und Bewertungskonfiguration legt die Anwendung keine Daten von selbst an.
