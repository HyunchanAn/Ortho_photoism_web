# -*- coding: utf-8 -*-
"""
Stage 2: Train Initial Extraoral Classifier/Landmark Model (from 3DFaceNorm / labeled data)
and Run Batch Pseudo-Labeling on Unlabeled Photos.

Fixes the tensor shape mismatch bug in legacy proto_model_trainer.py (where 90-degree profile
images have 5 landmarks [10 floats] and frontal/45/smile images have 6 landmarks [12 floats])
and supports hybrid MediaPipe Face Mesh + ResNet pseudo-labeling with automatic
`needs_review` flagging for human-in-the-loop correction.
"""

import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from PIL import ExifTags, Image
from torch.utils.data import DataLoader, Dataset
from torchvision import models, transforms

try:
    import mediapipe as mp
    HAS_MEDIAPIPE = True
except Exception:
    mp = None
    HAS_MEDIAPIPE = False


EXTRAORAL_TYPES = ["frontal", "angle_45", "angle_90", "smile"]
LANDMARKS_NORMAL = ["forehead", "left_pupil", "right_pupil", "nose_tip", "philtrum", "upper_lip"]
LANDMARKS_90 = ["forehead", "right_pupil", "nose_tip", "philtrum", "upper_lip"]


def apply_exif_orientation(image: Image.Image) -> Image.Image:
    try:
        if hasattr(image, "_getexif"):
            exif = image._getexif()
            if exif:
                for tag_id, tag_name in ExifTags.TAGS.items():
                    if tag_name == "Orientation" and tag_id in exif:
                        orientation = exif[tag_id]
                        if orientation == 3:
                            return image.rotate(180, expand=True)
                        if orientation == 6:
                            return image.rotate(270, expand=True)
                        if orientation == 8:
                            return image.rotate(90, expand=True)
    except Exception:
        pass
    return image


class PhotoClassifier(nn.Module):
    def __init__(self, num_classes: int = 4):
        super().__init__()
        self.resnet = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)
        in_features = self.resnet.fc.in_features
        self.resnet.fc = nn.Linear(in_features, num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.resnet(x)


class LandmarkDetector(nn.Module):
    """Compatible with Clinical_Photoism/proto_model_trainer.py state_dict."""

    def __init__(self):
        super().__init__()
        self.resnet = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)
        num_features = self.resnet.fc.in_features
        self.fc_90 = nn.Sequential(
            nn.Linear(num_features, 512),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(512, 10),
        )
        self.fc_normal = nn.Sequential(
            nn.Linear(num_features, 512),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(512, 12),
        )

    def forward(self, x: torch.Tensor, is_90_degree: bool = False) -> torch.Tensor:
        f = self.resnet.conv1(x)
        f = self.resnet.bn1(f)
        f = self.resnet.relu(f)
        f = self.resnet.maxpool(f)
        f = self.resnet.layer1(f)
        f = self.resnet.layer2(f)
        f = self.resnet.layer3(f)
        f = self.resnet.layer4(f)
        f = self.resnet.avgpool(f)
        f = torch.flatten(f, 1)
        return self.fc_90(f) if is_90_degree else self.fc_normal(f)


def scan_labeled_samples(data_dir: Path) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    all_samples: List[Dict] = []
    samples_90: List[Dict] = []
    samples_normal: List[Dict] = []

    for json_path in sorted(data_dir.glob("*.json")):
        img_path = None
        for ext in (".JPG", ".jpg", ".JPEG", ".jpeg", ".PNG", ".png"):
            candidate = json_path.with_suffix(ext)
            if candidate.exists():
                img_path = candidate
                break
        if img_path is None:
            continue

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except Exception:
            continue

        photo_type = meta.get("photo_type")
        landmarks = meta.get("landmarks", {})
        if photo_type not in EXTRAORAL_TYPES or not isinstance(landmarks, dict):
            continue

        req = LANDMARKS_90 if photo_type == "angle_90" else LANDMARKS_NORMAL
        if not all(k in landmarks for k in req):
            continue

        rec = {
            "img_path": str(img_path),
            "json_path": str(json_path),
            "photo_type": photo_type,
            "landmarks": landmarks,
            "required_landmarks": req,
        }
        all_samples.append(rec)
        if photo_type == "angle_90":
            samples_90.append(rec)
        else:
            samples_normal.append(rec)

    return all_samples, samples_normal, samples_90


class ClassificationDataset(Dataset):
    def __init__(self, samples: List[Dict], transform):
        self.samples = samples
        self.transform = transform

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int):
        s = self.samples[idx]
        img = apply_exif_orientation(Image.open(s["img_path"]).convert("RGB"))
        tensor_img = self.transform(img)
        label = EXTRAORAL_TYPES.index(s["photo_type"])
        return tensor_img, label


class LandmarkGroupDataset(Dataset):
    def __init__(self, samples: List[Dict], transform):
        self.samples = samples
        self.transform = transform

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int):
        s = self.samples[idx]
        img = apply_exif_orientation(Image.open(s["img_path"]).convert("RGB"))
        w, h = img.size
        coords: List[float] = []
        for k in s["required_landmarks"]:
            x, y = s["landmarks"][k]
            coords.extend([float(x) / max(w, 1), float(y) / max(h, 1)])
        return self.transform(img), torch.tensor(coords, dtype=torch.float32)


def train_pipeline(train_dir: Path, model_dir: Path, epochs: int = 35, batch_size: int = 16, lr: float = 1e-4):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[Train] Device: {device} | Loading dataset from {train_dir}")

    all_samples, samples_normal, samples_90 = scan_labeled_samples(train_dir)
    if not all_samples:
        raise ValueError(f"No valid (.jpg + .json) extraoral training pairs found in {train_dir}")

    print(
        f"[Train] Valid pairs: total={len(all_samples)} | normal(6-pt)={len(samples_normal)} | angle_90(5-pt)={len(samples_90)}"
    )

    tx = transforms.Compose(
        [
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ]
    )

    cls_loader = DataLoader(ClassificationDataset(all_samples, tx), batch_size=batch_size, shuffle=True)
    norm_loader = (
        DataLoader(LandmarkGroupDataset(samples_normal, tx), batch_size=batch_size, shuffle=True)
        if samples_normal
        else None
    )
    deg90_loader = (
        DataLoader(LandmarkGroupDataset(samples_90, tx), batch_size=max(2, min(batch_size, len(samples_90))), shuffle=True)
        if samples_90
        else None
    )

    classifier = PhotoClassifier(num_classes=len(EXTRAORAL_TYPES)).to(device)
    detector = LandmarkDetector().to(device)

    cls_opt = optim.AdamW(classifier.parameters(), lr=lr, weight_decay=1e-4)
    det_opt = optim.AdamW(detector.parameters(), lr=lr, weight_decay=1e-4)
    cls_crit = nn.CrossEntropyLoss()
    det_crit = nn.SmoothL1Loss()

    for epoch in range(1, epochs + 1):
        classifier.train()
        detector.train()
        cls_loss_sum, cls_correct, cls_total = 0.0, 0, 0
        for x, y in cls_loader:
            x, y = x.to(device), y.to(device)
            cls_opt.zero_grad()
            logits = classifier(x)
            loss = cls_crit(logits, y)
            loss.backward()
            cls_opt.step()
            cls_loss_sum += loss.item() * x.size(0)
            cls_correct += (logits.argmax(dim=1) == y).sum().item()
            cls_total += x.size(0)

        det_loss_sum, det_steps = 0.0, 0
        if norm_loader is not None:
            for x, pts in norm_loader:
                x, pts = x.to(device), pts.to(device)
                det_opt.zero_grad()
                pred = detector(x, is_90_degree=False)
                loss = det_crit(pred, pts)
                loss.backward()
                det_opt.step()
                det_loss_sum += loss.item()
                det_steps += 1

        if deg90_loader is not None:
            for x, pts in deg90_loader:
                x, pts = x.to(device), pts.to(device)
                det_opt.zero_grad()
                pred = detector(x, is_90_degree=True)
                loss = det_crit(pred, pts)
                loss.backward()
                det_opt.step()
                det_loss_sum += loss.item()
                det_steps += 1

        if epoch == 1 or epoch % 5 == 0 or epoch == epochs:
            acc = 100.0 * cls_correct / max(cls_total, 1)
            print(
                f"  Epoch [{epoch:02d}/{epochs:02d}] ClsLoss={cls_loss_sum/max(cls_total,1):.4f} Acc={acc:.1f}% | LandmarkLoss={det_loss_sum/max(det_steps,1):.5f}"
            )

    model_dir.mkdir(parents=True, exist_ok=True)
    cls_path = model_dir / "photo_classifier.pth"
    det_path = model_dir / "landmark_detector.pth"
    torch.save(classifier.state_dict(), cls_path)
    torch.save(detector.state_dict(), det_path)
    print(f"[Train Complete] Saved weights to:\n  - {cls_path}\n  - {det_path}")


def mediapipe_predict_extraoral(img_rgb: np.ndarray) -> Optional[Tuple[str, Dict[str, List[float]], float]]:
    """Fallback/hybrid MediaPipe Face Mesh landmark extractor for frontal/smile/45-degree views."""
    if not HAS_MEDIAPIPE or not hasattr(mp, "solutions") or not hasattr(mp.solutions, "face_mesh"):
        return None

    h, w, _ = img_rgb.shape
    with mp.solutions.face_mesh.FaceMesh(
        static_image_mode=True, max_num_faces=1, refine_landmarks=True, min_detection_confidence=0.3
    ) as fm:
        res = fm.process(img_rgb)
        if not res.multi_face_landmarks:
            return None
        lm = res.multi_face_landmarks[0].landmark

        def pt(idx: int) -> List[float]:
            return [round(float(lm[idx].x * w), 1), round(float(lm[idx].y * h), 1)]

        landmarks = {
            "forehead": pt(10),
            "left_pupil": pt(473),
            "right_pupil": pt(468),
            "nose_tip": pt(1),
            "philtrum": pt(164),
            "upper_lip": pt(13),
        }

        # Estimate yaw asymmetry & smile mouth opening
        lp_x, rp_x = landmarks["left_pupil"][0], landmarks["right_pupil"][0]
        nose_x = landmarks["nose_tip"][0]
        eye_dist = abs(lp_x - rp_x) + 1e-5
        eye_mid_x = 0.5 * (lp_x + rp_x)
        yaw_ratio = abs(nose_x - eye_mid_x) / eye_dist

        mouth_top_y = lm[13].y * h
        mouth_bot_y = lm[14].y * h
        mouth_left_x = lm[61].x * w
        mouth_right_x = lm[291].x * w
        mouth_open_ratio = abs(mouth_bot_y - mouth_top_y) / (abs(mouth_right_x - mouth_left_x) + 1e-5)

        if yaw_ratio > 0.55:
            photo_type = "angle_45"
            conf = 0.65
        elif mouth_open_ratio > 0.14:
            photo_type = "smile"
            conf = 0.80
        else:
            photo_type = "frontal"
            conf = 0.85

        return (photo_type, landmarks, conf)


def pseudo_label_directory(target_dir: Path, model_dir: Path, overwrite: bool = False):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    cls_path = model_dir / "photo_classifier.pth"
    det_path = model_dir / "landmark_detector.pth"

    has_trained_weights = cls_path.exists() and det_path.exists()
    classifier: Optional[PhotoClassifier] = None
    detector: Optional[LandmarkDetector] = None

    tx = transforms.Compose(
        [
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ]
    )

    if has_trained_weights:
        print(f"[Pseudo-Label] Loaded trained ResNet weights from {model_dir}")
        classifier = PhotoClassifier(num_classes=len(EXTRAORAL_TYPES)).to(device)
        detector = LandmarkDetector().to(device)
        classifier.load_state_dict(torch.load(cls_path, map_location=device))
        detector.load_state_dict(torch.load(det_path, map_location=device))
        classifier.eval()
        detector.eval()
    else:
        print("[Pseudo-Label] No trained ResNet weights found yet; using MediaPipe Face Mesh hybrid mode.")

    images = sorted(
        [p for p in target_dir.iterdir() if p.is_file() and p.suffix.lower() in (".jpg", ".jpeg", ".png")]
    )
    print(f"[Pseudo-Label] Processing {len(images)} images in {target_dir} ...")

    created, needs_review_cnt = 0, 0
    for img_path in images:
        json_path = img_path.with_suffix(".json")
        if json_path.exists() and not overwrite:
            continue

        pil_img = apply_exif_orientation(Image.open(img_path).convert("RGB"))
        w, h = pil_img.size
        img_rgb = np.array(pil_img)

        photo_type = "frontal"
        landmarks: Dict[str, List[float]] = {}
        confidence = 0.0
        source_method = "none"

        # 1. Try trained ResNet classifier + landmark detector first if available
        if classifier is not None and detector is not None:
            with torch.no_grad():
                x = tx(pil_img).unsqueeze(0).to(device)
                logits = classifier(x)
                probs = torch.softmax(logits, dim=1)[0]
                pred_idx = int(probs.argmax().item())
                confidence = float(probs[pred_idx].item())
                photo_type = EXTRAORAL_TYPES[pred_idx]
                is_90 = photo_type == "angle_90"
                raw_pts = detector(x, is_90_degree=is_90)[0].cpu().numpy().tolist()
                keys = LANDMARKS_90 if is_90 else LANDMARKS_NORMAL
                for i, k in enumerate(keys):
                    px = round(max(0.0, min(1.0, raw_pts[2 * i])) * w, 1)
                    py = round(max(0.0, min(1.0, raw_pts[2 * i + 1])) * h, 1)
                    landmarks[k] = [px, py]
                source_method = "resnet_trained"

        # 2. Refine or fallback with MediaPipe Face Mesh for non-90 views
        mp_res = mediapipe_predict_extraoral(img_rgb)
        if mp_res is not None:
            mp_type, mp_landmarks, mp_conf = mp_res
            if source_method == "none" or (photo_type != "angle_90" and confidence < 0.75):
                photo_type = mp_type
                landmarks = mp_landmarks
                confidence = max(confidence, mp_conf)
                source_method = "mediapipe_facemesh"

        # 3. If still empty (e.g., 90-degree profile without trained weights), place default template points for quick drag
        if not landmarks:
            photo_type = "angle_90"
            landmarks = {
                "forehead": [round(w * 0.68, 1), round(h * 0.25, 1)],
                "right_pupil": [round(w * 0.63, 1), round(h * 0.42, 1)],
                "nose_tip": [round(w * 0.75, 1), round(h * 0.54, 1)],
                "philtrum": [round(w * 0.70, 1), round(h * 0.62, 1)],
                "upper_lip": [round(w * 0.71, 1), round(h * 0.67, 1)],
            }
            confidence = 0.20
            source_method = "profile_template_fallback"

        needs_review = confidence < 0.80 or photo_type == "angle_90" or source_method == "profile_template_fallback"
        if needs_review:
            needs_review_cnt += 1

        payload = {
            "image_size": [h, w],
            "photo_type": photo_type,
            "landmarks": landmarks,
            "photo_category": "extraoral",
            "pseudo_label_meta": {
                "source": source_method,
                "confidence": round(confidence, 4),
                "needs_review": needs_review,
                "verified_by_human": False,
            },
        }
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        created += 1

    print(
        f"[Pseudo-Label Complete] Generated {created} JSON draft labels ({needs_review_cnt} flagged as needs_review)."
    )


def main():
    parser = argparse.ArgumentParser(
        description="Stage 2: Train extraoral model from 3DFaceNorm and batch pseudo-label new photos."
    )
    parser.add_argument(
        "--mode",
        choices=["train", "pseudo-label", "both"],
        default="pseudo-label",
        help="Run training, pseudo-labeling, or both",
    )
    parser.add_argument(
        "--train-dir",
        type=str,
        default=r"D:\Clinic_Dataset_Vault\training_folder_Extraoral",
        help="Directory with existing labeled (.JPG + .json) pairs (e.g. downloaded from Google Drive 3DFaceNorm)",
    )
    parser.add_argument(
        "--target-dir",
        type=str,
        default=r"D:\Clinic_Dataset_Vault\photos_color\extraoral_candidates",
        help="Directory with unlabeled photos to pseudo-label",
    )
    parser.add_argument(
        "--model-dir",
        type=str,
        default=r"D:\Github\Ortho_photoism_web\models",
        help="Directory to save/load photo_classifier.pth and landmark_detector.pth",
    )
    parser.add_argument("--epochs", type=int, default=35)
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing .json files")
    args = parser.parse_args()

    model_dir = Path(args.model_dir)
    if args.mode in ("train", "both"):
        train_pipeline(Path(args.train_dir), model_dir, epochs=args.epochs)
    if args.mode in ("pseudo-label", "both"):
        pseudo_label_directory(Path(args.target_dir), model_dir, overwrite=args.overwrite)


if __name__ == "__main__":
    main()
