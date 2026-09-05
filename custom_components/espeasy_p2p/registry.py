"""One way to find a unit's device-registry entry.

Two places needed the same lookup -- the coordinator when it removes a
node, the spatial layer when it asks where a unit hangs -- and both did it
with ``async_get_device(identifiers=...)``. Core deprecated that call: an
identifier is no longer unique across config entries, so it wants the
entry named, and the old call stops working in Home Assistant 2027.8.
The identifier here is our own, so the entries to ask are our own.

The lookup lives here rather than twice over, and it answers ``None`` for
every way it can fail -- no registry yet, no entry, no such unit. Both
callers already treated "not found" as an ordinary outcome.
"""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN


def device_for_unit(hass: HomeAssistant, unit: int) -> Any | None:
    """The registry entry for this unit, or ``None``.

    On installs older than 2025.9 the per-entry lookup does not exist yet;
    there the previous call is still the correct one. Which of the two is
    used is decided by asking the registry what it can do -- never by a
    version number.
    """
    identifier = (DOMAIN, f"unit-{unit}")
    try:
        registry = dr.async_get(hass)
        per_entry = getattr(registry, "async_get_device_by_identifier", None)
        if per_entry is None:  # pre-2025.9
            return registry.async_get_device(identifiers={identifier})
        for entry in hass.config_entries.async_entries(DOMAIN):
            device = per_entry(identifier, entry.entry_id)
            if device is not None:
                return device
        return None
    except (AttributeError, KeyError):  # pragma: no cover - registry absent
        return None
