#!/usr/bin/env python3
"""Offline verification for real-deploy joint CSV flow.

This script does not connect to DDS or robot hardware.
It simulates BeyondMimic execution and checks whether CSV is generated
when leaving BeyondMimic, without mixing in non-BeyondMimic states.
"""

import csv
import glob
import os
import tempfile
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

sys.path.append(str(Path(__file__).parent.parent.absolute()))

from common.joint_csv_logger import JointCsvLogger
from common.utils import FSMCommand, FSMStateName


def main() -> int:
    num_joints = 29
    target_policy = FSMStateName.SKILL_BEYOND_MIMIC
    model_stem = "2026-02-22_17-05-13_stand_experiment1"

    with tempfile.TemporaryDirectory(prefix="joint_csv_verify_") as tmp_dir:
        logger = JointCsvLogger(
            enabled=True,
            output_dir=tmp_dir,
            num_joints=num_joints,
            sample_stride=1,
            target_policy_names=[target_policy.name],
        )

        for i in range(10):
            q = np.linspace(-0.1, 0.1, num_joints, dtype=np.float32) + i * 0.01
            logger.on_policy_step(
                policy_name=FSMStateName.LOCOMODE,
                trigger_cmd=FSMCommand.INVALID,
                live_cmd=FSMCommand.INVALID,
                joint_positions=q,
            )

        for i in range(30):
            q = np.linspace(0.0, 1.0, num_joints, dtype=np.float32) + i * 0.01
            logger.on_policy_step(
                policy_name=target_policy,
                trigger_cmd=FSMCommand.SKILL_5,
                live_cmd=FSMCommand.INVALID,
                joint_positions=q,
                session_tag=model_stem,
            )

        q = np.linspace(0.5, 1.5, num_joints, dtype=np.float32)
        csv_path = logger.on_policy_step(
            policy_name=FSMStateName.SKILL_COOLDOWN,
            trigger_cmd=FSMCommand.INVALID,
            live_cmd=FSMCommand.INVALID,
            joint_positions=q,
        )

        if not csv_path:
            raise RuntimeError("CSV was not flushed when BeyondMimic ended")

        if not os.path.exists(csv_path):
            raise RuntimeError(f"CSV path not found: {csv_path}")

        csv_path_obj = Path(csv_path)
        if csv_path_obj.parent.parent.name != model_stem:
            raise RuntimeError(
                f"CSV was not placed under model folder: {csv_path_obj.parent.parent.name}"
            )

        if csv_path_obj.parent.name != datetime.now().strftime("%Y%m%d"):
            raise RuntimeError(
                f"CSV was not placed under current date folder: {csv_path_obj.parent.name}"
            )

        matched = glob.glob(os.path.join(tmp_dir, "joint_log_*.csv"))
        if len(matched) != 0:
            raise RuntimeError("Expected CSV files to be stored in model/date subdirectories")

        matched = glob.glob(os.path.join(tmp_dir, "*", "*", "joint_log_*.csv"))
        if len(matched) != 1:
            raise RuntimeError(f"Expected exactly 1 CSV file in model/date subdirectories, got {len(matched)}")

        with open(csv_path, "r", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        if len(rows) == 0:
            raise RuntimeError("CSV has no data rows")

        if len(rows) != 30:
            raise RuntimeError(f"Expected 30 BeyondMimic rows, got {len(rows)}")

        expected_cols = 4 + num_joints
        if len(reader.fieldnames or []) != expected_cols:
            raise RuntimeError(
                f"Unexpected column count: {len(reader.fieldnames or [])}, expected {expected_cols}"
            )

        if "q_00_rad" not in rows[0] or "q_28_rad" not in rows[0]:
            raise RuntimeError("Joint columns are incomplete")

        if any(row["policy"] != target_policy.name for row in rows):
            raise RuntimeError("CSV contains non-BeyondMimic policy rows")

        print("PASS: offline joint CSV flow verified")
        print(f"CSV: {csv_path}")
        print(f"Rows: {len(rows)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
