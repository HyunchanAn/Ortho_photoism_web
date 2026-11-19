# -*- coding: utf-8 -*-
"""
Stage 1: Organize, Filter Thumbnails, Classify Modality, and Anonymize Clinic Backup Data.

Features:
1. Filters out 80px software thumbnails (< 20 KB or height <= 120px) and non-image metadata (.ini, .w3d).
2. Reads .orig (DICOM 2D) headers and .jpg properties to classify images into:
   - photos_color/extraoral_candidates (face detected or extraoral aspect ratio)
   - photos_color/intraoral_candidates (intraoral clinical photos / intraoral camera)
   - panoramic (Modality=PX or panoramic aspect ratio >= 1.65)
   - cephalometric (Modality=DX or high-res cephalometric grayscale >= 2000x2000)
   - periapical (Modality=IO grayscale)
3. Strips all patient identifying filenames/paths and renames files to CASE_XXXX_IMG_YYYY.jpg.
4. Optionally exports anonymized 2D DICOM (.dcm) files with PHI tags removed (--export-clean-dicom).
"""

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Dict, Optional, Tuple

import cv2
import numpy as np

try:
    import pydicom
    HAS_PYDICOM = True
except ImportError:
    HAS_PYDICOM = False

try:
    import mediapipe as mp
    HAS_MEDIAPIPE = True
except ImportError:
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


def inspect_orig_dicom(orig_path: Path) -> Tuple[str, int, int, int]:
    """Return (Modality, SamplesPerPixel, Columns, Rows) from a .orig DICOM file if valid."""
    if not HAS_PYDICOM or not orig_path.exists():
        return ("UNK", 0, 0, 0)
    try:
        ds = pydicom.dcmread(str(orig_path), stop_before_pixels=True, force=True)
        mod = str(getattr(ds, "Modality", "UNK")).upper().strip()
        spp = int(getattr(ds, "SamplesPerPixel", 1))
        cols = int(getattr(ds, "Columns", 0))
        rows = int(getattr(ds, "Rows", 0))
        return (mod, spp, cols, rows)
    except Exception:
        return ("UNK", 0, 0, 0)


def anonymize_and_save_dicom(src_dicom: Path, dst_dicom: Path, anon_case_id: str) -> bool:
    if not HAS_PYDICOM or not src_dicom.exists():
        return False
    try:
        ds = pydicom.dcmread(str(src_dicom), force=True)
        for tag_name in PHI_DICOM_TAGS:
            if hasattr(ds, tag_name):
                setattr(ds, tag_name, "")
        ds.PatientID = anon_case_id
        ds.PatientName = anon_case_id
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
) -> Tuple[str, Optional[Path]]:
    """
    Classify a 2D image into one of:
    - 'photos_color/extraoral_candidates'
    - 'photos_color/intraoral_candidates'
    - 'panoramic'
    - 'cephalometric'
    - 'periapical'
    Returns (category_subpath, matching_orig_dicom_path_if_any).
    """
    h, w, _ = img_bgr.shape
    orig_candidate = jpg_path.with_suffix(".orig")
    if not orig_candidate.exists():
        # Sometimes named <stem>.jpg.orig
        alt_orig = Path(str(jpg_path) + ".orig")
        orig_candidate = alt_orig if alt_orig.exists() else orig_candidate

    mod, spp, _, _ = inspect_orig_dicom(orig_candidate)
    color = is_color_image(img_bgr) or (spp == 3)
    aspect = w / float(max(h, 1))

    if color:
        if face_detector.has_human_face(img_bgr):
            return ("photos_color/extraoral_candidates", orig_candidate if orig_candidate.exists() else None)
        return ("photos_color/intraoral_candidates", orig_candidate if orig_candidate.exists() else None)

    # Grayscale radiograph classification
    if mod == "PX" or (aspect >= 1.65 and w >= 1200):
        return ("panoramic", orig_candidate if orig_candidate.exists() else None)
    if mod == "DX" or (w >= 2000 and h >= 1800 and aspect < 1.65):
        return ("cephalometric", orig_candidate if orig_candidate.exists() else None)
    return ("periapical", orig_candidate if orig_candidate.exists() else None)


def main():
    parser = argparse.ArgumentParser(
        description="Organize, filter thumbnails, and anonymize clinic backup data."
    )
    parser.add_argument(
        "--src",
        type=str,
        default=r"D:\Github\Ortho_photoism_web\교정상담실_내원기록_백업",
        help="Source raw backup directory",
    )
    parser.add_argument(
        "--dst",
        type=str,
        default=r"D:\Clinic_Dataset_Vault",
        help="Destination anonymized dataset vault directory (outside Git repository)",
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
        "clean_dicoms_exported": 0,
    }

    min_bytes = int(args.min_size_kb * 1024)
    all_jpgs = sorted(src_root.rglob("*.jpg")) + sorted(src_root.rglob("*.jpeg")) + sorted(src_root.rglob("*.png"))
    print(f"[Stage 1] Scanning {len(all_jpgs)} image files from {src_root} ...")

    img_counter_per_case: Dict[str, int] = {}

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

        # Identify patient/case folder by top-level relative folder under src_root
        rel_parts = img_path.relative_to(src_root).parts
        raw_case_key = rel_parts[0] if len(rel_parts) > 1 else "ROOT_CASE"
        if raw_case_key not in case_map:
            case_counter += 1
            digest = hashlib.sha256(raw_case_key.encode("utf-8", errors="ignore")).hexdigest()[:6].upper()
            case_map[raw_case_key] = f"CASE_{case_counter:04d}_{digest}"

        anon_case_id = case_map[raw_case_key]
        img_counter_per_case[anon_case_id] = img_counter_per_case.get(anon_case_id, 0) + 1
        img_seq = img_counter_per_case[anon_case_id]

        category, orig_dicom = classify_2d_image(img_path, img_bgr, face_detector)
        stats[category] = stats.get(category, 0) + 1

        out_dir = dst_root / category
        out_dir.mkdir(parents=True, exist_ok=True)
        anon_stem = f"{anon_case_id}_IMG_{img_seq:04d}"
        out_jpg = out_dir / f"{anon_stem}.jpg"
        shutil.copy2(img_path, out_jpg)

        if args.export_clean_dicom and orig_dicom is not None and category in ("panoramic", "cephalometric", "periapical"):
            out_dcm = dst_root / f"{category}_dicom" / f"{anon_stem}.dcm"
            if anonymize_and_save_dicom(orig_dicom, out_dcm, anon_case_id):
                stats["clean_dicoms_exported"] += 1

        if idx % 200 == 0:
            print(f"  Processed {idx}/{len(all_jpgs)} files ... Current stats: {stats}")

    # Save private case mapping locally in dst_root (never commit to git)
    mapping_file = dst_root / "_private_case_mapping_DO_NOT_SHARE.json"
    with open(mapping_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "notice": "PRIVATE LOCAL MAPPING ONLY - DO NOT UPLOAD TO GITHUB OR CLOUD",
                "total_cases": case_counter,
                "stats": stats,
                "case_mapping": case_map,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    summary_file = dst_root / "dataset_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "total_cases": case_counter,
                "stats": stats,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    print("\n[Stage 1 Complete]")
    print(f"Destination Vault: {dst_root}")
    print(json.dumps(stats, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
