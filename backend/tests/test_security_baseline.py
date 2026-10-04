from __future__ import annotations

import base64
from io import BytesIO

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from jose import JWTError
from PIL import Image
from pydantic import ValidationError

from api.endpoints.chat import _ensure_session_access
from api.endpoints.reports import download_report_pdf
from api.schemas.requests import ChatRequest
from core.auth import AuthenticatedActor, decode_clerk_token, require_doctor
from core.config import settings
from main import create_app
from services.chat_store import chat_store
from services.patient_store import patient_store
from services.storage import StorageService, storage_service
from tools.utils import validate_xray_base64


DOCTOR = AuthenticatedActor(user_id="doctor-a", role="doctor")


def _image_data_url(image_format: str = "PNG") -> str:
    buffer = BytesIO()
    Image.new("RGB", (8, 8), "white").save(buffer, format=image_format)
    mime = "image/png" if image_format == "PNG" else "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(buffer.getvalue()).decode('ascii')}"


def _configure_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "clerk_jwt_key", "test-public-key")
    monkeypatch.setattr(settings, "clerk_issuer", "https://clerk.example")
    monkeypatch.setattr(settings, "clerk_authorized_parties", "http://localhost:3000")
    monkeypatch.setattr("core.auth.jwt.get_unverified_header", lambda _token: {"alg": "RS256"})


def test_valid_clerk_claims_create_doctor(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_auth(monkeypatch)
    monkeypatch.setattr(
        "core.auth.jwt.decode",
        lambda *_args, **_kwargs: {
            "sub": "doctor-a",
            "role": "doctor",
            "azp": "http://localhost:3000",
            "name": "Dr Test",
        },
    )

    actor = decode_clerk_token("token")

    assert actor == AuthenticatedActor("doctor-a", "doctor", "Dr Test")


@pytest.mark.parametrize(
    ("claims", "expected"),
    [
        ({"sub": "doctor-a", "role": "doctor", "azp": "https://evil.example"}, "unauthorized application"),
        ({"sub": "doctor-a", "role": "admin", "azp": "http://localhost:3000"}, "role has not been provisioned"),
        ({"sub": "doctor-a", "role": "doctor", "sts": "pending"}, "setup is incomplete"),
    ],
)
def test_invalid_clerk_claims_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
    claims: dict,
    expected: str,
) -> None:
    _configure_auth(monkeypatch)
    monkeypatch.setattr("core.auth.jwt.decode", lambda *_args, **_kwargs: claims)

    with pytest.raises(HTTPException) as exc:
        decode_clerk_token("token")

    assert exc.value.status_code == 401
    assert expected in str(exc.value.detail)


def test_bad_signature_or_expired_token_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_auth(monkeypatch)

    def fail_decode(*_args, **_kwargs):
        raise JWTError("signature, issuer, exp, or nbf check failed")

    monkeypatch.setattr("core.auth.jwt.decode", fail_decode)
    with pytest.raises(HTTPException) as exc:
        decode_clerk_token("token")
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_patient_role_cannot_enter_doctor_api() -> None:
    with pytest.raises(HTTPException) as exc:
        await require_doctor(AuthenticatedActor("patient-a", "patient"))
    assert exc.value.status_code == 403


def test_identity_and_multiple_attachment_forgery_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ChatRequest(message="analyze", actor_id="doctor-a", actor_role="doctor")
    with pytest.raises(ValidationError):
        ChatRequest(message="analyze", attachments=["one", "two"])


def test_deidentification_attestation_defaults_to_false() -> None:
    request = ChatRequest(message="analyze", attachment="image-data")
    assert request.deidentified_confirmed is False


def test_live_api_requires_bearer_token_and_storage_is_not_public() -> None:
    with TestClient(create_app()) as client:
        assert client.get("/api/reports/list").status_code == 401
        assert client.get("/storage/reports/example.pdf").status_code == 404


@pytest.mark.asyncio
async def test_chat_ownership_is_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    async def other_doctors_session(_chat_id: str):
        return {"chat_id": "chat-1", "doctor_id": "doctor-b"}

    monkeypatch.setattr(chat_store, "get_session", other_doctors_session)
    with pytest.raises(HTTPException) as exc:
        await _ensure_session_access("chat-1", DOCTOR.user_id)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_report_download_is_owner_scoped(monkeypatch: pytest.MonkeyPatch) -> None:
    async def no_owned_report(_report_id: str):
        return None

    monkeypatch.setattr(patient_store, "get_report", no_owned_report)
    with pytest.raises(HTTPException) as exc:
        await download_report_pdf("report-b", DOCTOR)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_report_download_rejects_another_doctors_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def other_doctors_report(_report_id: str):
        return {"report_id": "report-b", "doctor_user_id": "doctor-b"}

    monkeypatch.setattr(patient_store, "get_report", other_doctors_report)
    with pytest.raises(HTTPException) as exc:
        await download_report_pdf("report-b", DOCTOR)
    assert exc.value.status_code == 403


def test_authorized_report_download_succeeds(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    report = tmp_path / "reports" / "report-a.pdf"
    report.parent.mkdir()
    report.write_bytes(b"%PDF-test")

    async def owned_report(_report_id: str):
        return {
            "report_id": "report-a",
            "doctor_user_id": DOCTOR.user_id,
            "pdf_path": "reports/report-a.pdf",
        }

    monkeypatch.setattr(patient_store, "get_report", owned_report)
    monkeypatch.setattr(storage_service, "root", tmp_path)
    app = create_app()
    app.dependency_overrides[require_doctor] = lambda: DOCTOR

    with TestClient(app) as client:
        response = client.get("/api/reports/report-a/pdf")

    assert response.status_code == 200
    assert response.content == b"%PDF-test"
    assert response.headers["content-type"] == "application/pdf"


def test_request_body_limit_rejects_large_content_length() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/health",
            content=b"x",
            headers={"content-length": str(settings.max_request_bytes + 1)},
        )

    assert response.status_code == 413


def test_private_storage_rejects_traversal_and_deletes_owned_file(tmp_path) -> None:
    service = StorageService()
    service.root = tmp_path
    report = tmp_path / "reports" / "report.pdf"
    report.parent.mkdir()
    report.write_bytes(b"%PDF-test")

    assert service.resolve_private_path("../outside.pdf") is None
    assert service.resolve_private_path("reports/report.pdf") == report.resolve()


@pytest.mark.asyncio
async def test_private_storage_deletion(tmp_path) -> None:
    service = StorageService()
    service.root = tmp_path
    report = tmp_path / "reports" / "report.pdf"
    report.parent.mkdir()
    report.write_bytes(b"%PDF-test")

    assert await service.delete_reference("reports/report.pdf") is True
    assert not report.exists()


@pytest.mark.parametrize("image_format", ["PNG", "JPEG"])
def test_valid_xray_formats_are_accepted(image_format: str) -> None:
    assert validate_xray_base64(_image_data_url(image_format)).startswith(
        b"\x89PNG" if image_format == "PNG" else b"\xff\xd8"
    )


@pytest.mark.parametrize(
    "payload",
    [
        "https://example.com/xray.png",
        "data:image/png;base64,not-base64!",
        "data:application/pdf;base64,JVBERg==",
        base64.b64encode(b"PK\x03\x04zip").decode("ascii"),
        base64.b64encode(b"DICMdicom").decode("ascii"),
    ],
)
def test_unsupported_or_malformed_uploads_are_rejected(payload: str) -> None:
    with pytest.raises(ValueError):
        validate_xray_base64(payload)


def test_oversized_upload_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "max_xray_mb", 1)
    payload = base64.b64encode(b"x" * (1024 * 1024 + 1)).decode("ascii")
    with pytest.raises(ValueError, match="upload limit"):
        validate_xray_base64(payload)
