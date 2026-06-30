import sys
from pathlib import Path

import yaml
from ultralytics import YOLO
from ultralytics.data.utils import check_det_dataset

WORKSPACE = Path(__file__).resolve().parent
FIRE_SEG_DIR = WORKSPACE / "fire-seg"
DIVERSE_FALL_DIR = WORKSPACE / "DiverseFall10500_seg"
COMBINED_YAML = WORKSPACE / "combined.yaml"
RUNS_DIR = Path("runs")
RUN_NAME = "fire-seg"

EPOCHS = 30
IMG_SIZE = 480
LR0 = 0.001
FREEZE_LAYERS = 10
BASE_WEIGHTS = "yolo11n-seg.pt"
BASE_DATASET = "coco.yaml"

COCO_NAMES = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat", "traffic light",
    "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep", "cow",
    "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee",
    "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove", "skateboard", "surfboard", "tennis racket", "bottle",
    "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange",
    "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch", "potted plant", "bed",
    "dining table", "toilet", "tv", "laptop", "mouse", "remote", "keyboard", "cell phone", "microwave", "oven",
    "toaster", "sink", "refrigerator", "book", "clock", "vase", "scissors", "teddy bear", "hair drier", "toothbrush",
]


def resolve_split_path(root: Path, split_value) -> Path:
    if isinstance(split_value, list):
        first = split_value[0]
    else:
        first = split_value
    if isinstance(first, str):
        candidate = (root / first).resolve()
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Could not resolve split path under {root}: {split_value}")


def build_combined_yaml() -> Path:
    fire_train_img = FIRE_SEG_DIR / "images" / "train"
    fire_val_img = FIRE_SEG_DIR / "images" / "val"
    if not fire_train_img.exists() or not fire_val_img.exists():
        print(
            f"Fire seg dataset missing. Run prepare_dataset.py first.\n"
            f"  expected: {fire_train_img}",
            file=sys.stderr,
        )
        sys.exit(1)

    diverse_train_img = DIVERSE_FALL_DIR / "train" / "images"
    diverse_val_img = DIVERSE_FALL_DIR / "valid" / "images"
    if not diverse_train_img.exists() or not diverse_val_img.exists():
        print(
            f"DiverseFall10500_seg missing. Run convert_fall_labels.py first.\n"
            f"  expected: {diverse_train_img}",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Ensuring base dataset is available: {BASE_DATASET} (full COCO 2017 seg, ~20GB)")
    coco_info = check_det_dataset(BASE_DATASET)
    coco_root = Path(coco_info["path"])
    coco_train = resolve_split_path(coco_root, coco_info["train"])
    coco_val = resolve_split_path(coco_root, coco_info["val"])
    print(f"  COCO root : {coco_root}")
    print(f"  COCO train: {coco_train}")
    print(f"  COCO val  : {coco_val}")

    names = {i: n for i, n in enumerate(COCO_NAMES)}
    names[80] = "fire"
    names[81] = "fall"
    names[82] = "normal"

    data = {
        "train": [str(coco_train), str(fire_train_img), str(diverse_train_img)],
        "val": [str(coco_val), str(fire_val_img), str(diverse_val_img)],
        "names": names,
    }
    COMBINED_YAML.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    print(f"Wrote {COMBINED_YAML}")
    return COMBINED_YAML


def export_openvino(best_pt: Path, yaml_path: Path) -> None:
    if not best_pt.exists():
        print(f"best.pt not found: {best_pt}", file=sys.stderr)
        return
    print(f"\nExporting OpenVINO INT8 from {best_pt}")
    model = YOLO(str(best_pt))
    model.export(
        format="openvino",
        imgsz=IMG_SIZE,
        int8=True,
        data=str(yaml_path),
    )
    print(f"OpenVINO model exported next to {best_pt.parent}")


def main() -> int:
    yaml_path = build_combined_yaml()

    print(f"\nLoading base weights: {BASE_WEIGHTS}")
    model = YOLO(BASE_WEIGHTS)

    print(
        f"Training: epochs={EPOCHS}, imgsz={IMG_SIZE}, lr0={LR0}, "
        f"freeze={FREEZE_LAYERS}"
    )
    model.train(
        data=str(yaml_path),
        epochs=EPOCHS,
        imgsz=IMG_SIZE,
        lr0=LR0,
        freeze=FREEZE_LAYERS,
        project=str(RUNS_DIR),
        name=RUN_NAME,
        exist_ok=True,
        optimizer='SGD',  
        amp=False,       
        resume=True,
        cos_lr=True,
        patience=40
    )

    best_pt = RUNS_DIR / RUN_NAME / "weights" / "best.pt"
    print(f"\nBest weights: {best_pt}")

    export_openvino(best_pt, yaml_path)

    print(
        "\nDone. Deploy to LattePanda:\n"
        f"  1. Copy {best_pt} -> ../server-2/weights/fine-tuned.pt (fallback)\n"
        f"  2. Copy {best_pt.parent / (best_pt.stem + '_int8_openvino_model')}\n"
        f"     -> ../server-2/weights/fine-tuned_openvino_model (preferred, ~3x faster on Intel CPU)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
