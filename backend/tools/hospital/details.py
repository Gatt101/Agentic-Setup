from __future__ import annotations

from langchain_core.tools import tool

from tools.hospital.data import HOSPITALS


async def get_hospital_details_impl(hospital_id: str) -> dict:
    for hospital in HOSPITALS:
        if hospital["hospital_id"] == hospital_id:
            return {
                "name": hospital["name"],
                "address": hospital["address"],
                "services": hospital["services"],
                "phone": hospital["phone"],
                "rating": hospital["rating"],
                "er_available": hospital["er_available"],
            }
    return {
        "name": "Unknown",
        "address": "Unknown",
        "services": [],
        "phone": "",
        "rating": 0.0,
        "er_available": False,
    }


@tool("hospital_get_hospital_details")
async def get_hospital_details(hospital_id: str) -> dict:
    """Return details for one hospital id."""
    return await get_hospital_details_impl(hospital_id)


__all__ = ["get_hospital_details", "get_hospital_details_impl"]
