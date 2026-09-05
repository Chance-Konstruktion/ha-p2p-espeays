"""Die Geraetesuche, die Koordinator und Spatial-Ebene teilen.

``async_get_device(identifiers=...)`` ist abgekuendigt: eine Kennung ist
ueber Konfigurationseintraege hinweg nicht mehr eindeutig, deshalb will
Core den Eintrag genannt bekommen. Der alte Aufruf endet in Home
Assistant 2027.8 und schreibt bis dahin bei jedem Griff eine Warnung.

Die Suche liegt jetzt einmal in ``registry.py`` statt zweimal. Beide
Welten stehen hier: ein heutiger Core mit der Suche je Eintrag und ein
aelterer ohne sie -- die Untergrenze der Integration ist 2024.1.

Der letzte Test hat mit der Suche nichts zu tun und steht trotzdem hier:
er importiert den Koordinator. Diese Suite fasst ihn sonst nirgends an,
und ein Syntaxfehler in seinen Importzeilen ist ihr deshalb einmal
komplett entgangen -- gruener Lauf, kaputte Datei.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from espeasy_p2p_files import registry as modul  # noqa: E402 (conftest baut es)
from espeasy_p2p_files.const import DOMAIN

UNIT = 7
KENNUNG = (DOMAIN, f"unit-{UNIT}")


class _Hass:
    def __init__(self, *entry_ids):
        self.config_entries = SimpleNamespace(
            async_entries=lambda domain: [
                SimpleNamespace(entry_id=kennung) for kennung in entry_ids
            ]
            if domain == DOMAIN
            else []
        )


class _NeuesRegister:
    """Kann die Suche je Eintrag -- wie Core seit 2025.9."""

    def __init__(self, treffer: dict):
        self._treffer = treffer
        self.gefragt: list[tuple] = []

    def async_get_device_by_identifier(self, kennung, entry_id):
        self.gefragt.append((kennung, entry_id))
        return self._treffer.get(entry_id)

    def async_get_device(self, identifiers=None):  # pragma: no cover
        raise AssertionError("der abgekuendigte Weg darf hier nicht laufen")


class _AltesRegister:
    """Kennt nur den alten Aufruf -- wie Core vor 2025.9."""

    def __init__(self, geraet):
        self._geraet = geraet
        self.gefragt = None

    def async_get_device(self, identifiers=None):
        self.gefragt = identifiers
        return self._geraet


@pytest.fixture
def register(monkeypatch):
    """Setzt das Register, das ``device_for_unit`` zu sehen bekommt."""

    def _setzen(objekt):
        monkeypatch.setattr(modul.dr, "async_get", lambda hass: objekt,
                            raising=False)
        return objekt

    return _setzen


def test_sucht_im_eigenen_eintrag(register):
    geraet = object()
    reg = register(_NeuesRegister({"espeasy-1": geraet}))
    assert modul.device_for_unit(_Hass("espeasy-1"), UNIT) is geraet
    assert reg.gefragt == [(KENNUNG, "espeasy-1")]


def test_zweiter_eintrag_wird_auch_gefragt(register):
    geraet = object()
    reg = register(_NeuesRegister({"espeasy-2": geraet}))
    assert modul.device_for_unit(_Hass("espeasy-1", "espeasy-2"), UNIT) is geraet
    assert reg.gefragt == [(KENNUNG, "espeasy-1"), (KENNUNG, "espeasy-2")]


def test_unbekannte_unit_gibt_nichts(register):
    register(_NeuesRegister({}))
    assert modul.device_for_unit(_Hass("espeasy-1"), UNIT) is None


def test_rueckfall_auf_alten_core(register):
    geraet = object()
    reg = register(_AltesRegister(geraet))
    assert modul.device_for_unit(_Hass("espeasy-1"), UNIT) is geraet
    assert reg.gefragt == {KENNUNG}


def test_ohne_register_kein_absturz(register):
    """Vor dem Start gibt es kein Register -- das ist kein Fehlerfall."""
    register(None)
    assert modul.device_for_unit(_Hass("espeasy-1"), UNIT) is None


def test_jede_datei_der_integration_uebersetzt():
    """Jede Datei einmal durch den Uebersetzer.

    Der Koordinator braucht zum Importieren mehr Home Assistant, als
    diese Suite nachbaut -- deshalb faellt hier nur auf, ob seine Datei
    ueberhaupt uebersetzbar ist. Genau das hat gefehlt, als ein
    Importfehler mitten in einer Klammer stand und der Lauf gruen blieb.
    """
    import py_compile
    from pathlib import Path

    wurzel = Path(__file__).resolve().parent.parent / "custom_components"
    dateien = sorted(wurzel.rglob("*.py"))
    assert dateien, "keine Quelldateien gefunden -- der Pfad stimmt nicht"
    for datei in dateien:
        py_compile.compile(str(datei), doraise=True, cfile=str(datei) + "c")
