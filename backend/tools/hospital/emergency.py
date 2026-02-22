from __future__ import annotations

from langchain_core.tools import tool

from tools.hospital.data import EMERGENCY_CONTACTS


async def get_emergency_contacts_impl(location: str) -> dict:
    key = location.strip().lower()
    if key not in EMERGENCY_CONTACTS:
        key = "india"
    return EMERGENCY_CONTACTS[key]


@tool("hospital_get_emergency_contacts")
async def get_emergency_contacts(location: str) -> dict:
    """Get emergency contact numbers for a location."""
    return await get_emergency_contacts_impl(location)


__all__ = ["get_emergency_contacts", "get_emergency_contacts_impl"]
