#!/usr/bin/env python3
"""Offline verification for real-deploy joint CSV flow.

This script does not connect to DDS or robot hardware.
It simulates policy transitions and joint states, then checks whether
CSV is generated when transitioning from SKILL_* back to LOCOMODE.
"""

import csv
import glob
import os
import tempfile
import sys
from pathlib import Path

import numpy as np

sys.path.append(str(Path(__file__).parent.parent.absolute()))

from common.joint_csv_logger import JointCsvLogger
from common.utils import FSMCommand, FSMStateName


def main() -> int:
    num_joints = 29

    with tempfile.TemporaryDirectory(prefix="joint_csv_verify_") as tmp_dir:
        logger = JointCsvLogger(
            enabled=True,
            output_dir=tmp_dir,
            num_joints=num_joints,
            sample_stride=1,
        )

        # Simulate one skill execution window: SKILL_Dance -> SKILL_COOLDOWN -> LOCOMODE.
        for i in range(30):
            q = np.linspace(0.0, 1.0, num_joints, dtype=np.float32) + i * 0.01
            logger.on_policy_step(
                policy_name=FSMStateName.SKILL_Dance,
                trigger_cmd=FSMCommand.SKILL_1,
                live_cmd=FSMCommand.INVALID,
                joint_positions=q,
            )

        for i in range(15):
            q = np.linspace(0.2, 1.2, num_joints, dtype=np.float32) + i * 0.01
            logger.on_policy_step(
                policy_name=FSMStateName.SKILL_COOLDOWN,
                trigger_cmd=FSMCommand.INVALID,
                live_cmd=FSMCommand.INVALID,
                joint_positions=q,
            )

        q = np.linspace(0.5, 1.5, num_joints, dtype=np.float32)
        csv_path = logger.on_policy_step(
            policy_name=FSMStateName.LOCOMODE,
            trigger_cmd=FSMCommand.INVALID,
            live_cmd=FSMCommand.INVALID,
            joint_positions=q,
        )

        if not csv_path:
            raise RuntimeError("CSV was not flushed when policy returned to LOCOMODE")

        if not os.path.exists(csv_path):
            raise RuntimeError(f"CSV path not found: {csv_path}")

        matched = glob.glob(os.path.join(tmp_dir, "joint_log_*.csv"))
        if len(matched) != 1:
            raise RuntimeError(f"Expected exactly 1 CSV file, got {len(matched)}")

        with open(csv_path, "r", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        if len(rows) == 0:
            raise RuntimeError("CSV has no data rows")

        expected_cols = 4 + num_joints
        if len(reader.fieldnames or []) != expected_cols:
            raise RuntimeError(
                f"Unexpected column count: {len(reader.fieldnames or [])}, expected {expected_cols}"
            )

        if "q_00_rad" not in rows[0] or "q_28_rad" not in rows[0]:
            raise RuntimeError("Joint columns are incomplete")

        print("PASS: offline joint CSV flow verified")
        print(f"CSV: {csv_path}")
        print(f"Rows: {len(rows)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
