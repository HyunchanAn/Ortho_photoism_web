# -*- coding: utf-8 -*-
"""
Stage 3: Human-in-the-Loop (HiTL) Fast Landmark & View Labeler GUI.

Key upgrades over legacy Clinical_Photoism/proto_landmark_labeler.py:
1. Automatically loads existing/pseudo-labeled .json next to each image on open.
2. Direct point dragging: click and drag any existing landmark dot on canvas, or press 1..6 and click.
3. One-key save & advance: press Space or S to save in-place without blocking popup dialogs and jump to next image.
4. Review filter: toggle "Needs Review Only (F)" to jump strictly through low-confidence / 90-degree profile drafts.
5. Supports both Extraoral (4 photo types, 6 landmarks) and Intraoral (5 photo types, 8 landmarks).
"""

import argparse
import json
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional, Tuple

from PIL import ExifTags, Image, ImageTk


EXTRAORAL_LANDMARKS = {
    "forehead": {"name": "1: 이마선", "key": "1", "color": "#FF3B30"},
    "left_pupil": {"name": "2: 좌측 동공", "key": "2", "color": "#007AFF"},
    "right_pupil": {"name": "3: 우측 동공", "key": "3", "color": "#34C759"},
    "nose_tip": {"name": "4: 코끝", "key": "4", "color": "#FF9500"},
    "philtrum": {"name": "5: 인중", "key": "5", "color": "#AF52DE"},
    "upper_lip": {"name": "6: 상순 하단", "key": "6", "color": "#FFD60A"},
}

INTRAORAL_LANDMARKS = {
    "incisal_11": {"name": "1: #11 절단연", "key": "1", "color": "#FF3B30"},
    "incisal_21": {"name": "2: #21 절단연", "key": "2", "color": "#007AFF"},
    "cusp_13": {"name": "3: #13 교두", "key": "3", "color": "#34C759"},
    "cusp_23": {"name": "4: #23 교두", "key": "4", "color": "#FF9500"},
    "mbc_16": {"name": "5: #16 MBC", "key": "5", "color": "#AF52DE"},
    "mbc_26": {"name": "6: #26 MBC", "key": "6", "color": "#FFD60A"},
    "gingival_33": {"name": "7: #33 치은연", "key": "7", "color": "#5AC8FA"},
    "gingival_43": {"name": "8: #43 치은연", "key": "8", "color": "#FF2D55"},
}

EXTRAORAL_TYPES = {
    "frontal": {"name": "정면 (Q)", "key": "q"},
    "angle_45": {"name": "45도 측면 (W)", "key": "w"},
    "angle_90": {"name": "90도 측면 (E)", "key": "e"},
    "smile": {"name": "웃는 사진 (R)", "key": "r"},
}

INTRAORAL_TYPES = {
    "frontal": {"name": "정면 (Q)", "key": "q"},
    "right": {"name": "우측 (W)", "key": "w"},
    "left": {"name": "좌측 (E)", "key": "e"},
    "maxilla": {"name": "상악 (R)", "key": "r"},
    "mandible": {"name": "하악 (T)", "key": "t"},
}


class HiTLFastLabeler:
    def __init__(self, initial_dir: Optional[str] = None, category: str = "extraoral"):
        self.root = tk.Tk()
        self.root.title("HiTL Fast Landmark Labeler (Pseudo-Label Reviewer)")
        self.root.geometry("1280x860")

        self.category = category if category in ("extraoral", "intraoral") else "extraoral"
        self.current_dir: Optional[Path] = Path(initial_dir) if initial_dir else None
        self.all_files: List[Path] = []
        self.active_files: List[Path] = []
        self.idx: int = -1
        self.filter_needs_review_only = tk.BooleanVar(value=False)

        self.original_image: Optional[Image.Image] = None
        self.photo_image: Optional[ImageTk.PhotoImage] = None
        self.disp_scale: Tuple[float, float] = (1.0, 1.0)
        self.current_photo_type: Optional[str] = None
        self.current_landmark: Optional[str] = None
        # Stored in ORIGINAL image coordinates [x, y]
        self.landmarks_orig: Dict[str, List[float]] = {}
        self.pseudo_meta: Dict = {}
        self.dragging_landmark: Optional[str] = None
        self.dirty = False

        self._build_ui()
        self._bind_keys()

        if self.current_dir and self.current_dir.exists():
            self.load_directory(self.current_dir)

    def _active_schema(self):
        if self.category == "intraoral":
            return INTRAORAL_TYPES, INTRAORAL_LANDMARKS
        return EXTRAORAL_TYPES, EXTRAORAL_LANDMARKS

    def _build_ui(self):
        top_bar = tk.Frame(self.root, padx=8, pady=6)
        top_bar.pack(side=tk.TOP, fill=tk.X)

        tk.Button(top_bar, text="폴더 열기 (Ctrl+O)", command=self.choose_directory).pack(side=tk.LEFT, padx=4)
        tk.Button(top_bar, text="모드 전환 (구외/구내)", command=self.toggle_category).pack(side=tk.LEFT, padx=4)
        tk.Checkbutton(
            top_bar,
            text="검수 필요(needs_review/미검수)만 보기 (F)",
            variable=self.filter_needs_review_only,
            command=self.refresh_file_filter,
        ).pack(side=tk.LEFT, padx=8)

        tk.Button(top_bar, text="◀ 이전 (A/Left)", command=self.prev_image).pack(side=tk.LEFT, padx=4)
        tk.Button(
            top_bar,
            text="저장 및 다음 (Space / S)",
            bg="#28A745",
            fg="white",
            command=self.save_and_next,
        ).pack(side=tk.LEFT, padx=4)
        tk.Button(top_bar, text="다음 ▶ (D/Right)", command=self.next_image).pack(side=tk.LEFT, padx=4)

        self.info_label = tk.Label(top_bar, text="폴더를 선택하세요", font=("Arial", 10, "bold"))
        self.info_label.pack(side=tk.RIGHT, padx=8)

        body = tk.Frame(self.root)
        body.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.sidebar = tk.Frame(body, width=250, padx=8, pady=8)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)

        self.canvas = tk.Canvas(body, bg="#1E1E1E", cursor="crosshair")
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.canvas.bind("<ButtonPress-3>", self.on_right_click_delete_point)
        self.root.bind("<Configure>", lambda e: self.redraw_canvas())

        self._rebuild_sidebar_buttons()

    def _rebuild_sidebar_buttons(self):
        for child in self.sidebar.winfo_children():
            child.destroy()

        photo_types, landmarks = self._active_schema()
        tk.Label(
            self.sidebar,
            text=f"현재 모드: {'구외사진 (Extraoral)' if self.category == 'extraoral' else '구내사진 (Intraoral)'}",
            font=("Arial", 10, "bold"),
        ).pack(pady=4, anchor="w")

        type_box = tk.LabelFrame(self.sidebar, text="1. 사진 종류 선택 (Q/W/E/R/T)", padx=6, pady=6)
        type_box.pack(fill=tk.X, pady=6)
        self.type_buttons: Dict[str, tk.Button] = {}
        for k, info in photo_types.items():
            b = tk.Button(type_box, text=info["name"], command=lambda key=k: self.set_photo_type(key))
            b.pack(fill=tk.X, pady=2)
            self.type_buttons[k] = b

        lm_box = tk.LabelFrame(self.sidebar, text="2. 특징점 선택 (숫자키 또는 점 드래그)", padx=6, pady=6)
        lm_box.pack(fill=tk.X, pady=6)
        self.lm_buttons: Dict[str, tk.Button] = {}
        for k, info in landmarks.items():
            b = tk.Button(
                lm_box,
                text=info["name"],
                anchor="w",
                command=lambda key=k: self.set_current_landmark(key),
            )
            b.pack(fill=tk.X, pady=2)
            self.lm_buttons[k] = b

        help_box = tk.LabelFrame(self.sidebar, text="단축키 안내", padx=6, pady=6)
        help_box.pack(fill=tk.X, pady=8)
        tk.Label(
            help_box,
            justify=tk.LEFT,
            text=(
                "- 점 드래그: 기존 점을 마우스로 직접 이동\n"
                "- 우클릭: 선택한 점 삭제\n"
                "- 숫자 1~8: 찍을 특징점 선택\n"
                "- Q/W/E/R: 사진 종류 변경\n"
                "- Space / S: 즉시 저장 후 다음 사진\n"
                "- A / D: 이전 / 다음 사진\n"
                "- F: 미검수 사진만 필터 토글"
            ),
        ).pack(anchor="w")

    def _bind_keys(self):
        self.root.bind("<Control-o>", lambda e: self.choose_directory())
        self.root.bind("<space>", lambda e: self.save_and_next())
        self.root.bind("<Left>", lambda e: self.prev_image())
        self.root.bind("<Right>", lambda e: self.next_image())
        self.root.bind("<Key>", self.on_key_press)

    def toggle_category(self):
        self.category = "intraoral" if self.category == "extraoral" else "extraoral"
        self.current_landmark = None
        self._rebuild_sidebar_buttons()
        self.redraw_canvas()

    def choose_directory(self):
        d = filedialog.askdirectory(title="라벨링할 이미지 폴더 선택")
        if d:
            self.load_directory(Path(d))

    def load_directory(self, folder: Path):
        self.current_dir = folder
        self.all_files = sorted(
            [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in (".jpg", ".jpeg", ".png")]
        )
        self.refresh_file_filter()

    def _file_needs_review(self, img_path: Path) -> bool:
        json_path = img_path.with_suffix(".json")
        if not json_path.exists():
            return True
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            meta = data.get("pseudo_label_meta", {})
            if meta.get("verified_by_human") is True:
                return False
            return bool(meta.get("needs_review", True))
        except Exception:
            return True

    def refresh_file_filter(self):
        if self.filter_needs_review_only.get():
            self.active_files = [p for p in self.all_files if self._file_needs_review(p)]
        else:
            self.active_files = list(self.all_files)

        if not self.active_files:
            self.idx = -1
            self.original_image = None
            self.canvas.delete("all")
            self.info_label.config(text="표시할 이미지가 없습니다 (0/0)")
            return

        self.idx = 0
        self.open_current_image()

    def open_current_image(self):
        if self.idx < 0 or self.idx >= len(self.active_files):
            return
        img_path = self.active_files[self.idx]
        pil_img = Image.open(img_path).convert("RGB")
        try:
            if hasattr(pil_img, "_getexif") and pil_img._getexif():
                exif = dict(pil_img._getexif().items())
                for k, v in ExifTags.TAGS.items():
                    if v == "Orientation" and k in exif:
                        if exif[k] == 3:
                            pil_img = pil_img.rotate(180, expand=True)
                        elif exif[k] == 6:
                            pil_img = pil_img.rotate(270, expand=True)
                        elif exif[k] == 8:
                            pil_img = pil_img.rotate(90, expand=True)
        except Exception:
            pass

        self.original_image = pil_img
        self.landmarks_orig = {}
        self.current_photo_type = None
        self.pseudo_meta = {}
        self.dirty = False

        json_path = img_path.with_suffix(".json")
        if json_path.exists():
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                cat = data.get("photo_category")
                if cat in ("extraoral", "intraoral") and cat != self.category:
                    self.category = cat
                    self._rebuild_sidebar_buttons()
                self.current_photo_type = data.get("photo_type")
                raw_lms = data.get("landmarks", {})
                if isinstance(raw_lms, dict):
                    for k, pt in raw_lms.items():
                        if isinstance(pt, (list, tuple)) and len(pt) == 2:
                            self.landmarks_orig[k] = [float(pt[0]), float(pt[1])]
                self.pseudo_meta = data.get("pseudo_label_meta", {})
            except Exception as e:
                print(f"JSON load error: {e}")

        self._highlight_buttons()
        self.redraw_canvas()

    def _highlight_buttons(self):
        for k, b in self.type_buttons.items():
            b.config(bg="#4DA3FF" if k == self.current_photo_type else "SystemButtonFace")
        for k, b in self.lm_buttons.items():
            has_pt = k in self.landmarks_orig
            if k == self.current_landmark:
                b.config(bg="#FFD60A")
            elif has_pt:
                b.config(bg="#C3E6CB")
            else:
                b.config(bg="SystemButtonFace")

        if self.idx >= 0 and self.active_files:
            img_path = self.active_files[self.idx]
            verified = self.pseudo_meta.get("verified_by_human", False)
            conf = self.pseudo_meta.get("confidence", "-")
            status_tag = "검수완료" if verified else f"초안(conf={conf})"
            self.info_label.config(
                text=f"[{self.idx + 1}/{len(self.active_files)}] {img_path.name} | {status_tag}"
            )

    def redraw_canvas(self):
        self.canvas.delete("all")
        if self.original_image is None:
            return
        cw = max(200, self.canvas.winfo_width())
        ch = max(200, self.canvas.winfo_height())
        ow, oh = self.original_image.size
        scale = min(cw / float(ow), ch / float(oh))
        nw, nh = max(1, int(ow * scale)), max(1, int(oh * scale))
        self.disp_scale = (ow / float(nw), oh / float(nh))

        resized = self.original_image.resize((nw, nh), Image.Resampling.LANCZOS)
        self.photo_image = ImageTk.PhotoImage(resized)
        self.canvas.create_image(0, 0, image=self.photo_image, anchor=tk.NW)

        _, lm_schema = self._active_schema()
        sx, sy = self.disp_scale
        for k, (ox, oy) in self.landmarks_orig.items():
            dx, dy = ox / sx, oy / sy
            color = lm_schema.get(k, {}).get("color", "#FF3B30")
            label_text = lm_schema.get(k, {}).get("name", k)
            r = 6
            self.canvas.create_oval(dx - r, dy - r, dx + r, dy + r, fill=color, outline="white", width=2)
            self.canvas.create_text(dx + 12, dy - 8, text=label_text, fill=color, anchor="w", font=("Arial", 10, "bold"))

    def _find_nearest_landmark(self, canvas_x: float, canvas_y: float, threshold_px: float = 14.0) -> Optional[str]:
        sx, sy = self.disp_scale
        best_k, best_dist = None, threshold_px
        for k, (ox, oy) in self.landmarks_orig.items():
            dx, dy = ox / sx, oy / sy
            dist = ((dx - canvas_x) ** 2 + (dy - canvas_y) ** 2) ** 0.5
            if dist <= best_dist:
                best_dist = dist
                best_k = k
        return best_k

    def on_mouse_down(self, event):
        if self.original_image is None:
            return
        near_k = self._find_nearest_landmark(event.x, event.y)
        if near_k is not None:
            self.dragging_landmark = near_k
            self.current_landmark = near_k
            self._highlight_buttons()
            return

        if self.current_landmark:
            sx, sy = self.disp_scale
            self.landmarks_orig[self.current_landmark] = [round(event.x * sx, 1), round(event.y * sy, 1)]
            self.dragging_landmark = self.current_landmark
            self.dirty = True
            self._highlight_buttons()
            self.redraw_canvas()

    def on_mouse_drag(self, event):
        if self.dragging_landmark and self.original_image is not None:
            sx, sy = self.disp_scale
            ow, oh = self.original_image.size
            ox = max(0.0, min(float(ow), event.x * sx))
            oy = max(0.0, min(float(oh), event.y * sy))
            self.landmarks_orig[self.dragging_landmark] = [round(ox, 1), round(oy, 1)]
            self.dirty = True
            self.redraw_canvas()

    def on_mouse_up(self, event):
        self.dragging_landmark = None

    def on_right_click_delete_point(self, event):
        near_k = self._find_nearest_landmark(event.x, event.y, threshold_px=18.0)
        if near_k and near_k in self.landmarks_orig:
            del self.landmarks_orig[near_k]
            self.dirty = True
            self._highlight_buttons()
            self.redraw_canvas()

    def set_photo_type(self, photo_type: str):
        self.current_photo_type = photo_type
        self.dirty = True
        self._highlight_buttons()

    def set_current_landmark(self, lm_key: str):
        self.current_landmark = lm_key
        self._highlight_buttons()

    def on_key_press(self, event):
        key = (event.char or "").lower()
        if not key:
            return
        if key == "s":
            self.save_and_next()
            return
        if key == "a":
            self.prev_image()
            return
        if key == "d":
            self.next_image()
            return
        if key == "f":
            self.filter_needs_review_only.set(not self.filter_needs_review_only.get())
            self.refresh_file_filter()
            return

        photo_types, landmarks = self._active_schema()
        for pt_k, info in photo_types.items():
            if info["key"] == key:
                self.set_photo_type(pt_k)
                return
        for lm_k, info in landmarks.items():
            if info["key"] == key:
                self.set_current_landmark(lm_k)
                return

    def save_current(self) -> bool:
        if self.idx < 0 or self.idx >= len(self.active_files) or self.original_image is None:
            return False
        if not self.current_photo_type:
            messagebox.showwarning("사진 종류 미선택", "사진 종류(Q/W/E/R)를 먼저 선택해주세요.")
            return False

        img_path = self.active_files[self.idx]
        json_path = img_path.with_suffix(".json")
        ow, oh = self.original_image.size

        payload = {
            "image_size": [oh, ow],
            "photo_type": self.current_photo_type,
            "landmarks": self.landmarks_orig,
            "photo_category": self.category,
            "pseudo_label_meta": {
                "source": self.pseudo_meta.get("source", "human"),
                "confidence": 1.0,
                "needs_review": False,
                "verified_by_human": True,
            },
        }
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        self.dirty = False
        self.pseudo_meta = payload["pseudo_label_meta"]
        self._highlight_buttons()
        return True

    def save_and_next(self):
        if self.save_current():
            self.next_image()

    def next_image(self):
        if self.idx + 1 < len(self.active_files):
            self.idx += 1
            self.open_current_image()

    def prev_image(self):
        if self.idx - 1 >= 0:
            self.idx -= 1
            self.open_current_image()

    def run(self):
        self.root.mainloop()


def main():
    parser = argparse.ArgumentParser(description="Stage 3: HiTL Fast Landmark & View Labeler GUI.")
    parser.add_argument(
        "--dir",
        type=str,
        default=r"D:\Github\Ortho_photoism_data\refined_dataset\photos_color\extraoral_candidates",
        help="Initial image directory to open",
    )
    parser.add_argument(
        "--category",
        choices=["extraoral", "intraoral"],
        default="extraoral",
        help="Initial labeling category",
    )
    args = parser.parse_args()
    app = HiTLFastLabeler(initial_dir=args.dir, category=args.category)
    app.run()


if __name__ == "__main__":
    main()
