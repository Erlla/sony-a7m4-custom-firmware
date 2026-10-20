"""Recalculate published summaries from native patch Lab and histogram counts.

No photographs, devices or firmware required. This checks published aggregates;
it cannot independently reproduce image decoding without the original images.
"""
from pathlib import Path
import csv
import json
import numpy as np

from colour_metrics import delta_e00, histogram_metrics

HERE = Path(__file__).resolve().parent


def load(name):
    return json.loads((HERE / "data" / name).read_text("utf-8"))


def main():
    metrics = load("metrics.json")["pairs"]
    native = {p["id"]: p for p in load("native_patch_review.json")["pairs"]}
    with (HERE / "指标汇总.csv").open(encoding="utf-8-sig", newline="") as stream:
        summary = list(csv.DictReader(stream))
    with (HERE / "逐色块数据.csv").open(encoding="utf-8-sig", newline="") as stream:
        patch_csv = list(csv.DictReader(stream))
    assert len(metrics) == len(native) == len(summary) == 8 and len(patch_csv) == 192
    for pair, row in zip(metrics, summary):
        assert (pair["label"], pair["look"], pair["capture"]) == (row["方案"], row["外观"], row["照片编号"])
        hist = pair["full"]["histograms"]
        channels = [histogram_metrics(hist["camera"][c], hist["edit"][c]) for c in "RGB"]
        assert abs(np.mean([p["overlap_pct"] for p in channels]) - float(row["RGB交集均值_%"])) < 1e-10
        assert abs(np.mean([p["W1_code_values"] for p in channels]) - float(row["RGB_W1_码值"])) < 1e-10
        values = []
        for patch in native[pair["id"]]["patches"]:
            value = float(delta_e00(patch["mean_Lab_camera"], patch["mean_Lab_edit"]))
            values.append(value)
            assert abs(value - patch["deltaE00_of_mean_Lab"]) < 1e-10
            other = next(p for p in patch_csv if p["方案"] == pair["label"] and p["外观"] == pair["look"]
                         and int(p["色块ID"]) == patch["id"])
            assert abs(value - float(other["均色DE00"])) < 1e-10
        assert abs(np.mean(values) - float(row["原尺寸24块均色DE00均值"])) < 1e-10
        assert abs(max(values) - float(row["原尺寸最差色块DE00"])) < 1e-10
    print("PASS: 8 pairs, 192 patch DeltaE00 values, RGB histogram intersection/W1 and both CSVs")


if __name__ == "__main__":
    main()
