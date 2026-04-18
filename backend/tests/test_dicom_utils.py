from __future__ import annotations

from io import BytesIO
from zipfile import ZipFile

from pydicom.dataset import Dataset, FileDataset
from pydicom.uid import CTImageStorage, ExplicitVRLittleEndian, generate_uid

from tools.modality.dicom_utils import extract_dicom_files_from_zip_bytes, is_dicom, normalize_dicom_series


def _build_ct_slice(
    *,
    series_uid: str,
    study_uid: str,
    instance_number: int,
    z_position: float,
    image_type: list[str] | None = None,
) -> bytes:
    file_meta = Dataset()
    file_meta.MediaStorageSOPClassUID = CTImageStorage
    file_meta.MediaStorageSOPInstanceUID = generate_uid()
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    file_meta.ImplementationClassUID = generate_uid()

    ds = FileDataset(
        "slice.dcm",
        {},
        file_meta=file_meta,
        preamble=b"\0" * 128,
    )
    ds.is_little_endian = True
    ds.is_implicit_VR = False
    ds.SOPClassUID = file_meta.MediaStorageSOPClassUID
    ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
    ds.StudyInstanceUID = study_uid
    ds.SeriesInstanceUID = series_uid
    ds.SeriesDescription = "CT Ankle"
    ds.Modality = "CT"
    ds.PatientID = "patient-1"
    ds.Rows = 16
    ds.Columns = 16
    ds.InstanceNumber = instance_number
    ds.SeriesNumber = 1
    ds.AcquisitionNumber = 1
    ds.ImagePositionPatient = [0.0, 0.0, float(z_position)]
    ds.ImageOrientationPatient = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
    ds.ImageType = image_type or ["ORIGINAL", "PRIMARY", "AXIAL"]
    ds.PixelSpacing = [1.0, 1.0]
    ds.SliceThickness = 1.0
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0
    ds.PixelData = (b"\0\0") * (ds.Rows * ds.Columns)

    buffer = BytesIO()
    ds.save_as(buffer)
    return buffer.getvalue()


def test_normalize_dicom_series_keeps_largest_non_localizer_series() -> None:
    study_uid = generate_uid()
    primary_series_uid = generate_uid()
    scout_series_uid = generate_uid()

    primary_series = [
        _build_ct_slice(
            study_uid=study_uid,
            series_uid=primary_series_uid,
            instance_number=index,
            z_position=float(index),
        )
        for index in range(1, 6)
    ]
    scout_slice = _build_ct_slice(
        study_uid=study_uid,
        series_uid=scout_series_uid,
        instance_number=999,
        z_position=99.0,
        image_type=["LOCALIZER"],
    )

    normalized_entries, info = normalize_dicom_series([primary_series[3], scout_slice, *primary_series[:3], primary_series[4]])

    assert len(normalized_entries) == 5
    assert info["selected_series_instance_uid"] == primary_series_uid
    assert info["discarded_slice_count"] == 1
    assert [entry["metadata"]["instance_number"] for entry in normalized_entries] == [1, 2, 3, 4, 5]


def test_extract_dicom_files_from_zip_bytes_filters_non_dicom_members() -> None:
    dicom_a = _build_ct_slice(
        study_uid=generate_uid(),
        series_uid=generate_uid(),
        instance_number=1,
        z_position=0.0,
    )
    dicom_b = _build_ct_slice(
        study_uid=generate_uid(),
        series_uid=generate_uid(),
        instance_number=2,
        z_position=1.0,
    )

    archive_buffer = BytesIO()
    with ZipFile(archive_buffer, "w") as archive:
        archive.writestr("series/a.dcm", dicom_a)
        archive.writestr("series/b.dcm", dicom_b)
        archive.writestr("series/readme.txt", "not a dicom")

    extracted = extract_dicom_files_from_zip_bytes(archive_buffer.getvalue())

    assert len(extracted) == 2
    assert all(is_dicom(payload) for payload in extracted)
