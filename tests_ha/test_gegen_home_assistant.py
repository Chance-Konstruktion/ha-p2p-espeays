"""Der Spatial-Adapter gegen ein echtes Home Assistant.

Was diese Datei prueft und was nicht -- das gehoert an den Anfang, sonst
liest sich ein gruener Lauf hier groesser, als er ist.

Anders als die Suite in ``tests/`` steht hier nichts Nachgebautes vom
Home-Assistant-Kern: echtes ``hass``, echte Registries, echter Config
Entry. Was hier haelt, haelt gegen die Schnittstelle, die die Integration
im Haus wirklich vorfindet -- und die jede neue HA-Version brechen kann,
ohne dass ein nachgebauter Test etwas davon merkt.

Der Koordinator ist bewusst ein Doppel. Er ist Teil DIESER Integration,
kein fremdes Innenleben; ihn hier echt hochzufahren hiesse, ein
ESPEasy-Netz nachzustellen, und das koennte diese Datei nur behaupten,
nicht pruefen. Getestet wird also der Weg vom Koordinator zum Hub -- und
genau der laeuft ueber Home Assistants echte Bausteine.

Der teuerste Fehler in diesem Weg ist nicht ein falscher Knoten, sondern
eine Ausnahme in ``data()``: Der Hub verwirft dann **die ganze Ebene**
fuer diesen Durchlauf, nicht nur den einen Knoten. Deshalb steht der
leere Fall hier ganz vorn.
"""

from __future__ import annotations

import json

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from spatial_hub_conformance import check

from custom_components.espeasy_p2p.spatial import async_setup_spatial

EIGENE_DOMAIN = "espeasy_p2p"


class KoordinatorDoppel:
    """Genau das, was der Adapter vom Koordinator liest -- nicht mehr.

    Absichtlich kein Nachbau der ganzen Klasse: Ein Doppel, das mehr kann
    als gebraucht wird, faellt beim naechsten Umbau nicht auf, sondern
    deckt ihn zu.
    """

    def __init__(self, nodes=None, last_seen=None):
        self.name = "Home Assistant"
        self.unit = 0
        self.nodes = nodes or {}
        self.last_seen = last_seen or {}


@pytest.fixture
def eintrag(hass: HomeAssistant):
    eigener = MockConfigEntry(domain=EIGENE_DOMAIN, title="ESPEasy P2P")
    eigener.add_to_hass(hass)
    return eigener


def _registrierung(hass, eintrag, koordinator):
    async_setup_spatial(hass, eintrag, koordinator)
    providers = hass.data.get("spatial_hub_providers") or {}
    assert EIGENE_DOMAIN in providers, (
        f"Der Adapter hat sich nicht angemeldet. Vorhanden: {sorted(providers)}"
    )
    return providers[EIGENE_DOMAIN]


@pytest.fixture
def leer(hass: HomeAssistant, eintrag):
    return _registrierung(hass, eintrag, KoordinatorDoppel())


@pytest.fixture
def besetzt(hass: HomeAssistant, eintrag):
    """Zwei Einheiten, eine davon stumm -- der Fall mit Kanten."""
    return _registrierung(
        hass,
        eintrag,
        KoordinatorDoppel(
            nodes={1: {"name": "Keller"}, 2: {"name": "Dach"}},
            last_seen={1: 0.0},
        ),
    )


# ── Anmeldung ─────────────────────────────────────────────────────────


def test_der_adapter_meldet_sich_am_hub_an(leer):
    """Ohne Eintrag in hass.data existiert die Ebene fuer den Hub nicht."""
    assert leer["provider_id"] == EIGENE_DOMAIN
    assert leer["name"]
    assert callable(leer["data"])


@pytest.mark.parametrize("welche", ["leer", "besetzt"])
def test_die_anmeldung_haelt_den_hub_vertrag_ein(welche, request):
    """Der mitgelieferte Konformitaets-Satz, gegen ein echtes hass.

    Beide Zustaende, weil sie verschiedene Wege nehmen: ohne Einheiten
    gibt es keine Kanten, mit Einheiten schon -- und Kanten auf Knoten,
    die es nicht gibt, sind der Klassiker, der Grundrisse zerlegt.
    """
    probleme = check(request.getfixturevalue(welche))
    assert not probleme, "Verstoesse gegen den Hub-Vertrag:\n  " + "\n  ".join(probleme)


# ── Das Verhalten ─────────────────────────────────────────────────────


def test_ohne_einheiten_bleibt_die_ebene_leer_statt_kaputt(leer):
    """Kein Netz heisst leer -- nicht Ausnahme.

    Der teure Fehler waere ein Stapelabzug im Log statt "hier ist nichts":
    Der Hub wirft dann die ganze Ebene weg.
    """
    nutzlast = leer["data"]()
    assert nutzlast["edges"] == []
    # Der virtuelle Peer (Home Assistant selbst) steht immer da.
    assert [k["id"] for k in nutzlast["nodes"]]


def test_jede_kante_zeigt_auf_einen_knoten_den_es_gibt(besetzt):
    nutzlast = besetzt["data"]()
    ids = {k["id"] for k in nutzlast["nodes"]}
    for kante in nutzlast["edges"]:
        assert kante["source"] in ids, f"Kante ins Leere: {kante}"
        assert kante["target"] in ids, f"Kante ins Leere: {kante}"


def test_data_bleibt_ueber_wiederholte_abfragen_ruhig(besetzt):
    """Der Hub fragt im Takt. Ein Zustand, der beim ersten Aufruf angelegt
    und beim zweiten falsch gelesen wird, faellt sonst erst nach Minuten
    auf -- und dann im Betrieb."""
    erste = besetzt["data"]()
    for _ in range(3):
        weitere = besetzt["data"]()
    assert {k["id"] for k in erste["nodes"]} == {k["id"] for k in weitere["nodes"]}


def test_die_nutzlast_ueberlebt_den_websocket(besetzt):
    """Alles geht als JSON an den Browser. Ein datetime, ein set oder eine
    eigene Klasse in den Metadaten nimmt das ganze Modell mit -- fuer
    jeden Anbieter, nicht nur diesen."""
    json.dumps(besetzt["data"]())
