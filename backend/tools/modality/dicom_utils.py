from __future__ import annotations

import io
import tempfile
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any


def is_dicom(data: bytes) -> bool:
    if len(data) >= 132 and data[128:132] == b"DICM":
        return True

    try:
        import pydicom

        ds = pydicom.dcmread(io.BytesIO(data), stop_before_pixels=True, force=True)
    except Exception:
        return False

    required_markers = ("Modality", "SOPClassUID", "SeriesInstanceUID", "StudyInstanceUID")
    return any(hasattr(ds, marker) for marker in required_markers)


def read_dicom_metadata(data: bytes) -> dict[str, Any]:
    import pydicom

    ds = pydicom.dcmread(io.BytesIO(data), stop_before_pixels=True, force=True)
    raw_modality = str(getattr(ds, "Modality", "") or "").strip().upper()
    modality = {
        "CT": "ct",
        "MR": "mri",
        "CR": "xray",
        "DX": "xray",
        "RF": "xray",
        "XA": "xray",
        "DR": "xray",
    }.get(raw_modality, "unknown")

    def _maybe_float(value: Any) -> float | None:
        try:
            if isinstance(value, (list, tuple)):
                value = value[0]
            return float(value)
        except Exception:
            return None

    def _maybe_float_list(value: Any) -> list[float] | None:
        try:
            if value is None:
                return None
            values = list(value)
            if not values:
                return None
            return [float(item) for item in values]
        except Exception:
            return None

    image_type = [str(item).strip() for item in getattr(ds, "ImageType", []) if str(item).strip()]
    image_position = _maybe_float_list(getattr(ds, "ImagePositionPatient", None))
    image_orientation = _maybe_float_list(getattr(ds, "ImageOrientationPatient", None))
    acquisition_number = getattr(ds, "AcquisitionNumber", None)
    series_number = getattr(ds, "SeriesNumber", None)
    is_localizer = any(token.upper() in {"LOCALIZER", "SCOUT", "OVERVIEW"} for token in image_type)

    metadata: dict[str, Any] = {
        "modality": modality,
        "raw_modality_tag": raw_modality,
        "body_part_examined": str(getattr(ds, "BodyPartExamined", "") or "").strip(),
        "study_description": str(getattr(ds, "StudyDescription", "") or "").strip(),
        "series_description": str(getattr(ds, "SeriesDescription", "") or "").strip(),
        "patient_id_dicom": str(getattr(ds, "PatientID", "") or "").strip(),
        "patient_name_dicom": str(getattr(ds, "PatientName", "") or "").strip(),
        "instance_number": getattr(ds, "InstanceNumber", None),
        "slice_thickness_mm": _maybe_float(getattr(ds, "SliceThickness", None)),
        "window_center": _maybe_float(getattr(ds, "WindowCenter", None)),
        "window_width": _maybe_float(getattr(ds, "WindowWidth", None)),
        "rows": getattr(ds, "Rows", None),
        "columns": getattr(ds, "Columns", None),
        "samples_per_pixel": getattr(ds, "SamplesPerPixel", 1),
        "bits_allocated": getattr(ds, "BitsAllocated", 16),
        "sop_class_uid": str(getattr(ds, "SOPClassUID", "") or ""),
        "sop_instance_uid": str(getattr(ds, "SOPInstanceUID", "") or ""),
        "study_instance_uid": str(getattr(ds, "StudyInstanceUID", "") or ""),
        "series_instance_uid": str(getattr(ds, "SeriesInstanceUID", "") or ""),
        "series_number": series_number,
        "acquisition_number": acquisition_number,
        "image_type": image_type,
        "image_position_patient": image_position,
        "image_orientation_patient": image_orientation,
        "is_localizer": is_localizer,
    }

    pixel_spacing = getattr(ds, "PixelSpacing", None)
    if pixel_spacing is not None and len(pixel_spacing) >= 2:
        metadata["pixel_spacing_mm"] = [float(pixel_spacing[0]), float(pixel_spacing[1])]
    else:
        metadata["pixel_spacing_mm"] = None

    return metadata


def extract_dicom_files_from_zip_bytes(data: bytes) -> list[bytes]:
    dicom_files: list[bytes] = []

    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            payload = archive.read(info.filename)
            if is_dicom(payload):
                dicom_files.append(payload)

    return dicom_files


def _group_key_from_metadata(metadata: dict[str, Any]) -> tuple[str, str, int, int]:
    study_uid = str(metadata.get("study_instance_uid") or "unknown-study")
    series_uid = str(metadata.get("series_instance_uid") or "unknown-series")
    rows = int(metadata.get("rows") or 0)
    columns = int(metadata.get("columns") or 0)
    return (study_uid, series_uid, rows, columns)


def _slice_sort_key(entry: dict[str, Any]) -> tuple[int, float, int, str]:
    metadata = entry["metadata"]
    position = metadata.get("image_position_patient")
    if isinstance(position, list) and len(position) >= 3:
        axis_value = position[2]
        return (0, float(axis_value), int(metadata.get("instance_number") or 0), str(metadata.get("sop_instance_uid") or ""))

    instance_number = metadata.get("instance_number")
    return (
        1,
        float(instance_number or 0),
        int(metadata.get("acquisition_number") or 0),
        str(metadata.get("sop_instance_uid") or ""),
    )


def normalize_dicom_series(dicom_files: list[bytes]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not dicom_files:
        raise ValueError("No DICOM files were provided")

    entries = [{"bytes": payload, "metadata": read_dicom_metadata(payload)} for payload in dicom_files]

    groups: dict[tuple[str, str, int, int], list[dict[str, Any]]] = defaultdict(list)
    for entry in entries:
        groups[_group_key_from_metadata(entry["metadata"])].append(entry)

    def _group_score(group_entries: list[dict[str, Any]]) -> tuple[int, int, int, int]:
        usable_entries = sum(1 for entry in group_entries if not entry["metadata"].get("is_localizer"))
        positioned_entries = sum(
            1
            for entry in group_entries
            if isinstance(entry["metadata"].get("image_position_patient"), list)
            and len(entry["metadata"]["image_position_patient"]) >= 3
        )
        numbered_entries = sum(1 for entry in group_entries if entry["metadata"].get("instance_number") is not None)
        return (usable_entries, len(group_entries), positioned_entries, numbered_entries)

    selected_key, selected_entries = max(groups.items(), key=lambda item: _group_score(item[1]))

    filtered_entries = [
        entry for entry in selected_entries
        if not entry["metadata"].get("is_localizer")
    ] or list(selected_entries)

    deduplicated: list[dict[str, Any]] = []
    seen_sop_uids: set[str] = set()
    seen_positions: set[tuple[float, float, float]] = set()
    for entry in sorted(filtered_entries, key=_slice_sort_key):
        metadata = entry["metadata"]
        sop_uid = str(metadata.get("sop_instance_uid") or "").strip()
        if sop_uid and sop_uid in seen_sop_uids:
            continue
        position = metadata.get("image_position_patient")
        if isinstance(position, list) and len(position) >= 3:
            position_key = (round(position[0], 4), round(position[1], 4), round(position[2], 4))
            if position_key in seen_positions:
                continue
            seen_positions.add(position_key)
        if sop_uid:
            seen_sop_uids.add(sop_uid)
        deduplicated.append(entry)

    representative = deduplicated[0]["metadata"] if deduplicated else selected_entries[0]["metadata"]
    info = {
        "selected_study_instance_uid": selected_key[0],
        "selected_series_instance_uid": selected_key[1],
        "selected_series_number": representative.get("series_number"),
        "selected_series_description": representative.get("series_description"),
        "selected_modality": representative.get("modality"),
        "available_series_count": len(groups),
        "selected_slice_count": len(deduplicated),
        "discarded_slice_count": len(entries) - len(deduplicated),
    }

    return deduplicated, info


def dicom_bytes_to_image_data_url(data: bytes) -> str:
    import numpy as np
    import pydicom
    from PIL import Image

    from tools.utils import encode_image_base64

    ds = pydicom.dcmread(io.BytesIO(data), force=True)
    pixels = ds.pixel_array.astype(np.float32)

    if pixels.ndim > 2:
        pixels = pixels[0]

    intercept = float(getattr(ds, "RescaleIntercept", 0) or 0)
    slope = float(getattr(ds, "RescaleSlope", 1) or 1)
    pixels = pixels * slope + intercept

    window_center = getattr(ds, "WindowCenter", None)
    window_width = getattr(ds, "WindowWidth", None)
    try:
        if isinstance(window_center, (list, tuple)):
            window_center = window_center[0]
        if isinstance(window_width, (list, tuple)):
            window_width = window_width[0]
        if window_center is not None and window_width not in (None, 0):
            center = float(window_center)
            width = max(float(window_width), 1.0)
            lower = center - width / 2.0
            upper = center + width / 2.0
            pixels = np.clip(pixels, lower, upper)
    except Exception:
        pass

    min_val = float(pixels.min())
    max_val = float(pixels.max())
    if max_val > min_val:
        pixels = (pixels - min_val) / (max_val - min_val)
    else:
        pixels = np.zeros_like(pixels)

    if str(getattr(ds, "PhotometricInterpretation", "") or "").upper() == "MONOCHROME1":
        pixels = 1.0 - pixels

    image = Image.fromarray((pixels * 255).astype(np.uint8), mode="L").convert("RGB")
    return f"data:image/png;base64,{encode_image_base64(image)}"


def normalize_body_part(body_part_examined: str, study_description: str = "", series_description: str = "") -> str:
    combined = f"{body_part_examined} {study_description} {series_description}".lower()
    mapping = [
        (["knee", "patella"], "knee"),
        (["spine", "spinal", "lumbar", "thoracic", "cervical", "vertebr", "disc"], "spine"),
        (["foot", "ankle", "calcaneus", "talus", "tarsal", "metatarsal"], "foot"),
        (["pelvis", "hip", "sacrum", "iliac", "acetabulum"], "pelvis"),
        (["shoulder", "clavicle", "scapula", "humerus"], "shoulder"),
        (["hand", "wrist", "carpal", "metacarpal", "phalanx", "finger"], "hand"),
        (["leg", "tibia", "fibula", "femur"], "leg"),
        (["elbow", "forearm", "ulna", "radius"], "elbow"),
    ]
    for keywords, part in mapping:
        if any(keyword in combined for keyword in keywords):
            return part
    return "unknown"


def dicom_bytes_to_nifti_file(dicom_data: bytes, output_path: str) -> tuple[str, dict[str, Any]]:
    import SimpleITK as sitk

    with tempfile.TemporaryDirectory(prefix="orthoassist_dicom_single_") as temp_dir:
        source_path = Path(temp_dir) / "input.dcm"
        source_path.write_bytes(dicom_data)
        image = sitk.ReadImage(str(source_path))
        sitk.WriteImage(image, output_path)
        info = {
            "size": list(image.GetSize()),
            "spacing": list(image.GetSpacing()),
            "origin": list(image.GetOrigin()),
            "direction": list(image.GetDirection()),
            "pixel_type": str(image.GetPixelIDTypeAsString()),
            "slice_count": int(image.GetDepth() or 1),
        }
    return output_path, info


def dicom_series_to_nifti_file(dicom_files: list[bytes], output_path: str) -> tuple[str, dict[str, Any]]:
    import SimpleITK as sitk

    normalized_entries, normalization_info = normalize_dicom_series(dicom_files)
    if len(normalized_entries) < 2:
        raise ValueError("Unable to assemble a volumetric series from the uploaded DICOM files")

    with tempfile.TemporaryDirectory(prefix="orthoassist_dicom_series_") as temp_dir:
        file_paths: list[str] = []
        for index, entry in enumerate(normalized_entries):
            path = Path(temp_dir) / f"slice_{index:04d}.dcm"
            path.write_bytes(entry["bytes"])
            file_paths.append(str(path))

        reader = sitk.ImageSeriesReader()
        reader.SetFileNames(file_paths)
        reader.MetaDataDictionaryArrayUpdateOn()
        reader.LoadPrivateTagsOn()
        image = reader.Execute()
        sitk.WriteImage(image, output_path)
        info = {
            "size": list(image.GetSize()),
            "spacing": list(image.GetSpacing()),
            "origin": list(image.GetOrigin()),
            "direction": list(image.GetDirection()),
            "pixel_type": str(image.GetPixelIDTypeAsString()),
            "slice_count": len(file_paths),
            **normalization_info,
        }
    return output_path, info
