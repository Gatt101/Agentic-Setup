from __future__ import annotations

from langchain_core.tools import tool

from services.storage import storage_service


async def upload_image_to_storage_impl(image_base64: str, filename: str, patient_id: str) -> dict:
    """Persist original image payload and return storage metadata."""
    saved = await storage_service.save_base64_image(
        image_base64=image_base64,
        filename=filename,
        patient_id=patient_id,
        subdir="raw",
    )
    return {
        "image_url": saved["public_url"],
        "public_id": saved["public_id"],
        "storage_path": saved["path"],
    }


@tool("vision_upload_image_to_storage")
async def upload_image_to_storage(image_base64: str, filename: str, patient_id: str) -> dict:
    """Upload image to configured storage backend."""
    return await upload_image_to_storage_impl(image_base64, filename, patient_id)


__all__ = ["upload_image_to_storage", "upload_image_to_storage_impl"]
