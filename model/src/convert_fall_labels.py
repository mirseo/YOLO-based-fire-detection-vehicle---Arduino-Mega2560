import random
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "DiverseFall10500"
DST = ROOT / "DiverseFall10500_seg"

CLASS_REMAP = {0: 81, 1: 82}
SPLITS = ["train", "valid"]


def make_junction(link: Path, target: Path) -> None:
    if link.exists() or link.is_symlink():
        return
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        check=True,
        shell=False,
    )


def convert_line(line: str) -> str | None:
    tokens = line.strip().split()
    if len(tokens) != 5:
        return None
    try:
        cls = int(tokens[0])
        cx, cy, w, h = map(float, tokens[1:])
    except ValueError:
        return None
    new_cls = CLASS_REMAP.get(cls)
    if new_cls is None:
        return None
    x1 = max(0.0, min(1.0, cx - w / 2))
    y1 = max(0.0, min(1.0, cy - h / 2))
    x2 = max(0.0, min(1.0, cx + w / 2))
    y2 = max(0.0, min(1.0, cy + h / 2))
    return f"{new_cls} {x1:.6f} {y1:.6f} {x2:.6f} {y1:.6f} {x2:.6f} {y2:.6f} {x1:.6f} {y2:.6f}"


def convert_split(split: str) -> int:
    src_labels = SRC / split / "labels"
    dst_labels = DST / split / "labels"
    dst_labels.mkdir(parents=True, exist_ok=True)

    src_img = SRC / split / "images"
    dst_img = DST / split / "images"
    make_junction(dst_img, src_img)

    count = 0
    for src_file in src_labels.glob("*.txt"):
        lines = src_file.read_text(encoding="utf-8").splitlines()
        converted = [convert_line(l) for l in lines]
        converted = [l for l in converted if l is not None]
        (dst_labels / src_file.name).write_text("\n".join(converted), encoding="utf-8")
        count += 1
    return count


def validate(split: str, sample_size: int = 50) -> tuple[int, int]:
    dst_labels = DST / split / "labels"
    files = list(dst_labels.glob("*.txt"))
    sample = random.sample(files, min(sample_size, len(files)))
    passed = 0
    failed = 0
    for f in sample:
        ok = True
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            tokens = line.split()
            if len(tokens) != 9:
                ok = False
                break
            if tokens[0] not in ("81", "82"):
                ok = False
                break
            try:
                coords = [float(t) for t in tokens[1:]]
            except ValueError:
                ok = False
                break
            if not all(0.0 <= c <= 1.0 for c in coords):
                ok = False
                break
        if ok:
            passed += 1
        else:
            failed += 1
    return passed, failed


def main() -> int:
    totals: dict[str, int] = {}
    for split in SPLITS:
        n = convert_split(split)
        totals[split] = n
        print(f"{split}: {n} files converted")

    passed, failed = validate("train")
    print(f"Validation (train, n=50): {passed} passed, {failed} failed")

    print(
        f"Conversion complete. "
        + ", ".join(f"{s}: {totals[s]}" for s in SPLITS)
        + f". Validation: {passed}/50 passed."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
