"""Bindet die skriptartigen Tests an pytest an.

Die Testmodule prüfen mit einem eigenen ``check()``-Helfer, der fehlgeschlagene
Prüfungen nur in einer modulweiten Liste (``failures`` bzw. ``FAILURES``)
sammelt; ausgewertet wird sie sonst erst im ``__main__``-Block. Unter pytest
leeren wir die Liste vor jedem Test und lassen den Test fehlschlagen, wenn
danach etwas darin steht.
"""

import pytest

FAILURE_LISTS = ("failures", "FAILURES")


def _failure_list(module):
    for name in FAILURE_LISTS:
        value = getattr(module, name, None)
        if isinstance(value, list):
            return value
    return None


@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item):
    failures = _failure_list(getattr(item, "module", None))
    if failures is None:
        return (yield)

    failures.clear()
    result = yield
    if failures:
        lines = "\n".join(f"  - {f}" for f in failures)
        raise AssertionError(f"{len(failures)} Prüfung(en) fehlgeschlagen:\n{lines}")
    return result
