# Herkunft

Angepasst aus [giantswarm/spec-driven-development](https://github.com/giantswarm/spec-driven-development), Datei `.agents/skills/contrarian/SKILL.md`, Stand Commit `2056d284f58a179b885b63d79b1f1ba048f3162a`. Lizenz: Apache License 2.0, siehe [LICENSE](LICENSE).

## Änderungen gegenüber dem Original

- Ins Deutsche übertragen und auf dieses Projekt zugeschnitten.
- Der Spec ist ein GitHub-Issue statt `<plan-dir>/SPEC.md`; das Urteil wird als Kommentar an dieses Issue geschrieben statt als Datei unter `<plan-dir>/contrarian/`.
- Durchsucht wird dieses Repository statt geklonter Fremdprojekte unter `.agents_source/`.
- Glossar ist `GLOSSARY.md` statt `context/glossary.md`.
- Der einfachste Weg schließt Lösungen ohne Code ein (Bewertungskonfiguration, Sonderfall, Excel-Export, Handgriff der Belegungskommission).
- Neuer Angriff „Regelkonflikt“ gegen `docs/Vergabegrundsaetze.md` und die ADRs; `KILL` auch bei Widerspruch zu den Vergabegrundsätzen.
- Der simulierte Einwand kommt von der Belegungskommission statt vom Reviewer der betroffenen Komponenten.
- Bezüge auf `/ground-truth` und `/to-website` entfernt; das Tor liegt vor `/to-tickets` und führt zurück zu `/grill-with-docs`.
- Ausdrückliche Fertig-Kriterien je Schritt ergänzt.
