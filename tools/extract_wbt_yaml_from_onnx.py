#!/usr/bin/env python
from __future__ import annotations

import argparse
from pathlib import Path

import onnx
import yaml


def _parse_csv_floats(raw: str) -> list[float]:
    return [float(x) for x in str(raw).split(",") if x.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract fallback params from whole_body_tracking-exported ONNX.")
    parser.add_argument("--onnx", required=True, help="Path to exported policy.onnx")
    parser.add_argument("--yaml", required=True, help="Path to WbtDance.yaml to update")
    args = parser.parse_args()

    onnx_path = Path(args.onnx)
    yaml_path = Path(args.yaml)

    model = onnx.load(str(onnx_path))
    meta = {p.key: p.value for p in model.metadata_props}

    required = ["default_joint_pos", "joint_stiffness", "joint_damping", "action_scale"]
    missing = [k for k in required if k not in meta]
    if missing:
        raise SystemExit(f"Missing metadata keys in ONNX: {missing}")

    with yaml_path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    cfg.setdefault("fallback", {})
    cfg["fallback"]["default_joint_pos"] = _parse_csv_floats(meta["default_joint_pos"])
    cfg["fallback"]["joint_stiffness"] = _parse_csv_floats(meta["joint_stiffness"])
    cfg["fallback"]["joint_damping"] = _parse_csv_floats(meta["joint_damping"])
    cfg["fallback"]["action_scale"] = _parse_csv_floats(meta["action_scale"])

    with yaml_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, sort_keys=False, allow_unicode=True)

    print(f"updated: {yaml_path}")


if __name__ == "__main__":
    main()
