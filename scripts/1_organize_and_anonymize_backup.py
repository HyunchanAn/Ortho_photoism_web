# -*- coding: utf-8 -*-
"""
Stage 1: Organize, Filter Thumbnails, Classify Modality, Extract Age/Sex, and Anonymize Clinic Backup Data.

Features:
1. Filters out 80px software thumbnails (< 20 KB or height <= 120px) and non-image metadata (.ini, .w3d).
2. Reads .orig (DICOM 2D) headers and .jpg properties to classify images into:
   - photos_color/extraoral_candidates (face detected or extraoral aspect ratio)
   - photos_color/intraoral_candidates (intraoral clinical photos / intraoral camera)
   - panoramic (Modality=PX or panoramic aspect ratio >= 1.65)
   - cephalometric (Modality=DX or high-res cephalometric grayscale >= 2000x2000)
   - periapical (Modality=IO grayscale)
3. Computes exact chronological age at scan time (age_years = (StudyDate - PatientBirthDate) / 365.2425)
   and biological sex (M/F) from .orig DICOM headers, writes anonymized dataset_manifest.csv, and discards raw dates.
4. Strips all patient identifying filenames/paths and renames files to CASE_XXXX_IMG_YYYY.jpg.
5. Optionally exports anonymized 2D DICOM (.dcm) files with PHI tags removed (--export-clean-dicom).
"""

import argparse
import csv
from datetime import datetime
import hashlib
import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

try:
    import pydicom
    HAS_PYDICOM = True
except ImportError:
    HAS_PYDICOM = False

try:
    from google.protobuf import message_factory, symbol_database
    if not hasattr(symbol_database.SymbolDatabase, "GetPrototype"):
        symbol_database.SymbolDatabase.GetPrototype = staticmethod(message_factory.GetMessageClass)
    if not hasattr(message_factory.MessageFactory, "GetPrototype"):
        message_factory.MessageFactory.GetPrototype = staticmethod(message_factory.GetMessageClass)
    import mediapipe as mp
    from mediapipe.python import solution_base
    solution_base.SolutionBase._modify_calculator_options = lambda self, proto, params: None
    HAS_MEDIAPIPE = True
except Exception:
    mp = None
    HAS_MEDIAPIPE = False


PHI_DICOM_TAGS = [
    "PatientName",
    "PatientID",
    "PatientBirthDate",
    "PatientSex",
    "PatientAge",
    "PatientAddress",
    "PatientTelephoneNumbers",
    "OtherPatientIDs",
    "OtherPatientNames",
    "InstitutionName",
    "InstitutionAddress",
    "ReferringPhysicianName",
    "PerformingPhysicianName",
    "OperatorsName",
    "AccessionNumber",
    "StudyID",
]


def read_image_safe(path: Path) -> Optional[np.ndarray]:
    try:
        buf = np.fromfile(str(path), dtype=np.uint8)
        if buf.size == 0:
            return None
        return cv2.imdecode(buf, cv2.IMREAD_COLOR)
    except Exception:
        return None


def _parse_dicom_date(date_str: str) -> Optional[datetime]:
    s = (date_str or "").strip().replace("-", "").replace(".", "")
    if len(s) >= 8 and s[:8].isdigit():
        try:
            return datetime.strptime(s[:8], "%Y%m%d")
        except ValueError:
            return None
    return None


def inspect_orig_dicom(orig_path: Path) -> Tuple[str, int, int, int, Optional[float], str]:
    """
    Return (Modality, SamplesPerPixel, Columns, Rows, age_years, sex)
    from a .orig DICOM file if valid. Raw birth/study dates are never returned or stored.
    """
    if not HAS_PYDICOM or not orig_path.exists():
        return ("UNK", 0, 0, 0, None, "U")
    try:
        ds = pydicom.dcmread(str(orig_path), stop_before_pixels=True, force=True)
        mod = str(getattr(ds, "Modality", "UNK")).upper().strip() or "UNK"
        spp = int(getattr(ds, "SamplesPerPixel", 1))
        cols = int(getattr(ds, "Columns", 0))
        rows = int(getattr(ds, "Rows", 0))

        raw_sex = str(getattr(ds, "PatientSex", "")).upper().strip()
        sex = raw_sex if raw_sex in ("M", "F") else "U"

        dob = _parse_dicom_date(str(getattr(ds, "PatientBirthDate", "")))
        study_dt = (
            _parse_dicom_date(str(getattr(ds, "StudyDate", "")))
            or _parse_dicom_date(str(getattr(ds, "ContentDate", "")))
            or _parse_dicom_date(str(getattr(ds, "AcquisitionDate", "")))
        )

        age_years: Optional[float] = None
        if dob and study_dt and study_dt >= dob:
            days = (study_dt - dob).days
            if 0 < days < 36525:
                age_years = round(days / 365.2425, 2)
        return (mod, spp, cols, rows, age_years, sex)
    except Exception:
        return ("UNK", 0, 0, 0, None, "U")


def anonymize_and_save_dicom(
    src_dicom: Path,
    dst_dicom: Path,
    anon_case_id: str,
    age_years: Optional[float] = None,
    sex: str = "U",
) -> bool:
    if not HAS_PYDICOM or not src_dicom.exists():
        return False
    try:
        ds = pydicom.dcmread(str(src_dicom), force=True)
        for tag_name in PHI_DICOM_TAGS:
            if hasattr(ds, tag_name):
                setattr(ds, tag_name, "")
        ds.PatientID = anon_case_id
        ds.PatientName = anon_case_id
        if sex in ("M", "F"):
            ds.PatientSex = sex
        if age_years is not None:
            ds.PatientAge = f"{int(round(age_years)):03d}Y"
        ds.remove_private_tags()
        dst_dicom.parent.mkdir(parents=True, exist_ok=True)
        ds.save_as(str(dst_dicom))
        return True
    except Exception:
        return False


def is_color_image(img_bgr: np.ndarray) -> bool:
    diff_bg = np.mean(np.abs(img_bgr[:, :, 0].astype(np.int16) - img_bgr[:, :, 1].astype(np.int16)))
    diff_gr = np.mean(np.abs(img_bgr[:, :, 1].astype(np.int16) - img_bgr[:, :, 2].astype(np.int16)))
    return (diff_bg + diff_gr) > 5.0


class ExtraoralDetector:
    def __init__(self):
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_alt.xml"
        )
        self.profile_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_profileface.xml"
        )
        self.mp_face = None
        if HAS_MEDIAPIPE and hasattr(mp, "solutions") and hasattr(mp.solutions, "face_detection"):
            self.mp_face = mp.solutions.face_detection.FaceDetection(
                model_selection=1, min_detection_confidence=0.35
            )

    def has_human_face(self, img_bgr: np.ndarray) -> bool:
        h, w, _ = img_bgr.shape
        if self.mp_face is not None:
            rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
            res = self.mp_face.process(rgb)
            if res and res.detections:
                return True
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        scale = min(1.0, 800.0 / max(h, w))
        if scale < 1.0:
            gray = cv2.resize(gray, (int(w * scale), int(h * scale)))
        faces = self.face_cascade.detectMultiScale(gray, 1.1, 4)
        if len(faces) > 0:
            return True
        profiles = self.profile_cascade.detectMultiScale(gray, 1.1, 4)
        if len(profiles) > 0:
            return True
        flipped = cv2.flip(gray, 1)
        profiles_flip = self.profile_cascade.detectMultiScale(flipped, 1.1, 4)
        return len(profiles_flip) > 0


def classify_2d_image(
    jpg_path: Path,
    img_bgr: np.ndarray,
    face_detector: ExtraoralDetector,
) -> Tuple[str, Optional[Path], str, Optional[float], str]:
    """
    Classify a 2D image into one of:
    - 'photos_color/extraoral_candidates'
    - 'photos_color/intraoral_candidates'
    - 'panoramic'
    - 'cephalometric'
    - 'periapical'
    Returns (category_subpath, matching_orig_dicom_path, modality_code, age_years, sex).
    """
    h, w, _ = img_bgr.shape
    orig_candidate = jpg_path.with_suffix(".orig")
    if not orig_candidate.exists():
        alt_orig = Path(str(jpg_path) + ".orig")
        orig_candidate = alt_orig if alt_orig.exists() else orig_candidate

    mod, spp, _, _, age_years, sex = inspect_orig_dicom(orig_candidate)
    color = is_color_image(img_bgr) or (spp == 3)
    aspect = w / float(max(h, 1))
    valid_orig = orig_candidate if orig_candidate.exists() else None

    if color:
        if face_detector.has_human_face(img_bgr):
            return ("photos_color/extraoral_candidates", valid_orig, mod, age_years, sex)
        return ("photos_color/intraoral_candidates", valid_orig, mod, age_years, sex)

    if mod == "PX" or (aspect >= 1.65 and w >= 1200):
        return ("panoramic", valid_orig, "PX" if mod == "UNK" else mod, age_years, sex)
    if mod == "DX" or (w >= 2000 and h >= 1800 and aspect < 1.65):
        return ("cephalometric", valid_orig, "DX" if mod == "UNK" else mod, age_years, sex)
    return ("periapical", valid_orig, "IO" if mod == "UNK" else mod, age_years, sex)


def main():
    parser = argparse.ArgumentParser(
        description="Organize, filter thumbnails, extract age/sex, and anonymize clinic backup data."
    )
    parser.add_argument(
        "--src",
        type=str,
        default=r"D:\Github\Ortho_photoism_data\교정상담실_내원기록_백업",
        help="Source raw backup directory",
    )
    parser.add_argument(
        "--dst",
        type=str,
        default=r"D:\Github\Ortho_photoism_data\refined_dataset",
        help="Destination anonymized dataset vault directory",
    )
    parser.add_argument(
        "--min-size-kb",
        type=float,
        default=20.0,
        help="Minimum JPG size in KB to exclude software thumbnails (default: 20 KB)",
    )
    parser.add_argument(
        "--min-height",
        type=int,
        default=120,
        help="Minimum image height in pixels to exclude 80px thumbnails (default: 120)",
    )
    parser.add_argument(
        "--export-clean-dicom",
        action="store_true",
        help="Also export PHI-stripped 2D DICOM (.dcm) files alongside .jpg for radiographs",
    )
    args = parser.parse_args()

    src_root = Path(args.src)
    dst_root = Path(args.dst)
    if not src_root.exists():
        raise FileNotFoundError(f"Source directory not found: {src_root}")

    dst_root.mkdir(parents=True, exist_ok=True)
    face_detector = ExtraoralDetector()

    case_map: Dict[str, str] = {}
    case_counter = 0
    stats = {
        "skipped_thumbnails": 0,
        "skipped_unreadable": 0,
        "photos_color/extraoral_candidates": 0,
        "photos_color/intraoral_candidates": 0,
        "panoramic": 0,
        "cephalometric": 0,
        "periapical": 0,
        "with_valid_age": 0,
        "clean_dicoms_exported": 0,
    }

    min_bytes = int(args.min_size_kb * 1024)
    all_jpgs = sorted(src_root.rglob("*.jpg")) + sorted(src_root.rglob("*.jpeg")) + sorted(src_root.rglob("*.png"))
    print(f"[Stage 1] Scanning {len(all_jpgs)} image files from {src_root} ...")

    img_counter_per_case: Dict[str, int] = {}
    manifest_rows: List[Dict[str, object]] = []

    for idx, img_path in enumerate(all_jpgs, 1):
        try:
            if img_path.stat().st_size < min_bytes:
                stats["skipped_thumbnails"] += 1
                continue
        except OSError:
            continue

        img_bgr = read_image_safe(img_path)
        if img_bgr is None:
            stats["skipped_unreadable"] += 1
            continue

        h, w, _ = img_bgr.shape
        if h <= args.min_height or w <= args.min_height:
            stats["skipped_thumbnails"] += 1
            continue

        rel_parts = img_path.relative_to(src_root).parts
        raw_case_key = rel_parts[0] if len(rel_parts) > 1 else "ROOT_CASE"
        if raw_case_key not in case_map:
            case_counter += 1
            digest = hashlib.sha256(raw_case_key.encode("utf-8", errors="ignore")).hexdigest()[:6].upper()
            case_map[raw_case_key] = f"CASE_{case_counter:04d}_{digest}"

        anon_case_id = case_map[raw_case_key]
        img_counter_per_case[anon_case_id] = img_counter_per_case.get(anon_case_id, 0) + 1
        img_seq = img_counter_per_case[anon_case_id]

        category, orig_dicom, mod_code, age_years, sex = classify_2d_image(img_path, img_bgr, face_detector)
        stats[category] = stats.get(category, 0) + 1
        if age_years is not None:
            stats["with_valid_age"] += 1

        out_dir = dst_root / category
        out_dir.mkdir(parents=True, exist_ok=True)
        anon_stem = f"{anon_case_id}_IMG_{img_seq:04d}"
        out_jpg = out_dir / f"{anon_stem}.jpg"
        shutil.copy2(img_path, out_jpg)

        if args.export_clean_dicom and orig_dicom is not None and category in ("panoramic", "cephalometric", "periapical"):
            out_dcm = dst_root / f"{category}_dicom" / f"{anon_stem}.dcm"
            if anonymize_and_save_dicom(orig_dicom, out_dcm, anon_case_id, age_years=age_years, sex=sex):
                stats["clean_dicoms_exported"] += 1

        manifest_rows.append(
            {
                "anon_image_id": anon_stem,
                "case_id": anon_case_id,
                "category": category,
                "modality": mod_code,
                "width": w,
                "height": h,
                "age_years": "" if age_years is None else age_years,
                "sex": sex,
                "rel_path": f"{category}/{anon_stem}.jpg",
            }
        )

        if idx % 500 == 0:
            print(f"  Processed {idx}/{len(all_jpgs)} files ... Current stats: {stats}")

    manifest_csv = dst_root / "dataset_manifest.csv"
    with open(manifest_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "anon_image_id",
                "case_id",
                "category",
                "modality",
                "width",
                "height",
                "age_years",
                "sex",
                "rel_path",
            ],
        )
        writer.writeheader()
        writer.writerows(manifest_rows)

    summary_file = dst_root / "dataset_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "total_cases": case_counter,
                "total_extracted_images": len(manifest_rows),
                "stats": stats,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    print("\n[Stage 1 Complete]")
    print(f"Destination Vault: {dst_root}")
    print(f"Total Anonymized Cases: {case_counter} | Total Usable 2D Images: {len(manifest_rows)}")
    print(json.dumps(stats, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
