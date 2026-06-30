import json
import sys
from pathlib import Path

import numpy as np
from ultralytics import SAM

WORKSPACE = Path(__file__).resolve().parent
DATASET_ROOT = WORKSPACE / "Fire Dataset for YOLOv8.v2i.coco"
OUTPUT_ROOT = WORKSPACE / "fire-seg"
SPLITS = {"train": "train", "valid": "val", "test": "test"}
FIRE_CLASS_ID = 80
SAM_MODEL = "sam_b.pt"


def coco_bbox_to_xyxy(bbox):
    x, y, w, h = bbox
    return [float(x), float(y), float(x + w), float(y + h)]


def normalize_polygon(polygon: np.ndarray, img_w: int, img_h: int) -> list:
    flat = []
    for x, y in polygon:
        nx = max(0.0, min(1.0, float(x) / img_w))
        ny = max(0.0, min(1.0, float(y) / img_h))
        flat.extend([nx, ny])
    return flat


def convert_split(sam: SAM, split_dir: Path, out_split: str) -> int:
    ann_path = split_dir / "_annotations.coco.json"
    if not ann_path.exists():
        print(f"Skip (no annotations): {split_dir}")
        return 0

    with ann_path.open(encoding="utf-8") as f:
        coco = json.load(f)

    images_by_id = {img["id"]: img for img in coco["images"]}
    cat_name = {c["id"]: c["name"].lower() for c in coco["categories"]}

    anns_by_image: dict[int, list[dict]] = {}
    for ann in coco["annotations"]:
        if cat_name.get(ann["category_id"], "") != "fire":
            continue
        anns_by_image.setdefault(ann["image_id"], []).append(ann)

    img_out = OUTPUT_ROOT / "images" / out_split
    lbl_out = OUTPUT_ROOT / "labels" / out_split
    img_out.mkdir(parents=True, exist_ok=True)
    lbl_out.mkdir(parents=True, exist_ok=True)

    written = 0
    skipped = 0
    for image_id, img_meta in images_by_id.items():
        anns = anns_by_image.get(image_id, [])
        if not anns:
            skipped += 1
            continue
        src_img = split_dir / img_meta["file_name"]
        if not src_img.exists():
            skipped += 1
            continue

        img_w = int(img_meta["width"])
        img_h = int(img_meta["height"])
        bboxes = [coco_bbox_to_xyxy(a["bbox"]) for a in anns]

        result = sam.predict(str(src_img), bboxes=bboxes, verbose=False)[0]
        if result.masks is None or result.masks.xy is None or len(result.masks.xy) == 0:
            skipped += 1
            continue

        label_lines = []
        for poly in result.masks.xy:
            if poly is None or len(poly) < 3:
                continue
            coords = normalize_polygon(poly, img_w, img_h)
            if len(coords) < 6:
                continue
            parts = [str(FIRE_CLASS_ID)] + [f"{c:.6f}" for c in coords]
            label_lines.append(" ".join(parts))

        if not label_lines:
            skipped += 1
            continue

        dst_img = img_out / src_img.name
        dst_img.write_bytes(src_img.read_bytes())
        lbl_path = lbl_out / (src_img.stem + ".txt")
        lbl_path.write_text("\n".join(label_lines) + "\n", encoding="utf-8")
        written += 1

        if written % 50 == 0:
            print(f"  [{out_split}] {written} written...")

    print(f"[{out_split}] wrote={written} skipped={skipped}")
    return written


def main() -> int:
    if not DATASET_ROOT.exists():
        print(f"Dataset not found: {DATASET_ROOT}", file=sys.stderr)
        return 1
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    print(f"Loading SAM model: {SAM_MODEL}")
    sam = SAM(SAM_MODEL)

    total = 0
    for src, dst in SPLITS.items():
        total += convert_split(sam, DATASET_ROOT / src, dst)

    print(f"\nDone. total={total}")
    print(f"Output: {OUTPUT_ROOT}")
    print("\nNext: run train.py to fine-tune yolo11n-seg with rehearsal.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
