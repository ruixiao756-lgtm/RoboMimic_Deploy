import csv
import os
import time
from datetime import datetime
from typing import Iterable, Optional, Sequence, Set


class JointCsvLogger:
    def __init__(
        self,
        enabled: bool,
        output_dir: str,
        num_joints: int,
        sample_stride: int = 1,
        target_policy_names: Optional[Sequence[str]] = None,
    ):
        self.enabled = bool(enabled)
        self.output_dir = output_dir
        self.num_joints = int(num_joints)
        self.sample_stride = max(1, int(sample_stride))
        self.target_policy_names = self._normalize_policy_names(target_policy_names)

        self._active = False
        self._rows = []
        self._start_time = 0.0
        self._start_policy = ""
        self._start_cmd = ""
        self._session_tag = ""
        self._start_datetime = None
        self._episode_id = 0
        self._loop_idx = 0

        if self.enabled:
            os.makedirs(self.output_dir, exist_ok=True)
            if self.target_policy_names is None:
                print(f"[JointCSV] Enabled. Output dir: {self.output_dir}")
            else:
                targets = ", ".join(sorted(self.target_policy_names))
                print(f"[JointCSV] Enabled for [{targets}]. Output dir: {self.output_dir}")

    @staticmethod
    def _name(x) -> str:
        return x.name if hasattr(x, "name") else str(x)

    @classmethod
    def _normalize_policy_names(cls, policy_names: Optional[Sequence[str]]) -> Optional[Set[str]]:
        if policy_names is None:
            return None

        if isinstance(policy_names, str):
            policy_names = [policy_names]

        return {cls._name(policy_name) for policy_name in policy_names}

    @staticmethod
    def _is_skill_policy_name(policy_name: str) -> bool:
        return policy_name.startswith("SKILL_")

    def _should_record_policy(self, policy_name: str) -> bool:
        if self.target_policy_names is None:
            return self._is_skill_policy_name(policy_name)
        return policy_name in self.target_policy_names

    @staticmethod
    def _normalize_session_tag(session_tag: Optional[str]) -> str:
        if session_tag is None:
            return ""

        normalized = str(session_tag).strip()
        if not normalized:
            return ""

        normalized = normalized.replace(os.sep, "_")
        if os.altsep:
            normalized = normalized.replace(os.altsep, "_")
        return normalized

    @property
    def active(self) -> bool:
        return self._active

    def _start(self, policy_name: str, trigger_cmd_name: str, session_tag: Optional[str] = None) -> None:
        self._active = True
        self._rows = []
        self._start_time = time.time()
        self._start_datetime = datetime.now()
        self._start_policy = policy_name
        self._start_cmd = trigger_cmd_name
        self._session_tag = self._normalize_session_tag(session_tag)
        self._loop_idx = 0
        if self._session_tag:
            print(
                f"[JointCSV] Start recording from policy={policy_name}, cmd={trigger_cmd_name}, "
                f"session={self._session_tag}"
            )
        else:
            print(f"[JointCSV] Start recording from policy={policy_name}, cmd={trigger_cmd_name}")

    def _resolve_output_dir(self) -> str:
        if not self._session_tag:
            return self.output_dir

        if self._start_datetime is None:
            date_dir = datetime.now().strftime("%Y%m%d")
        else:
            date_dir = self._start_datetime.strftime("%Y%m%d")

        return os.path.join(self.output_dir, self._session_tag, date_dir)

    def _append_row(self, policy_name: str, live_cmd_name: str, joint_positions: Iterable[float]) -> None:
        if (self._loop_idx % self.sample_stride) != 0:
            self._loop_idx += 1
            return

        now = time.time()
        row = {
            "unix_time": now,
            "elapsed_s": now - self._start_time,
            "policy": policy_name,
            "skill_cmd": live_cmd_name,
        }

        q = list(joint_positions)
        if len(q) != self.num_joints:
            raise ValueError(f"joint_positions length={len(q)} does not match num_joints={self.num_joints}")

        for i in range(self.num_joints):
            row[f"q_{i:02d}_rad"] = float(q[i])

        self._rows.append(row)
        self._loop_idx += 1

    def _flush(self, reason: str) -> str:
        self._active = False
        if len(self._rows) == 0:
            print(f"[JointCSV] No samples collected, skip file write. reason={reason}")
            return ""

        self._episode_id += 1
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = self._resolve_output_dir()
        os.makedirs(output_dir, exist_ok=True)
        file_name = (
            f"joint_log_{ts}_ep{self._episode_id:03d}_"
            f"{self._start_policy}_{self._start_cmd}_to_{reason}.csv"
        )
        file_path = os.path.join(output_dir, file_name)

        fieldnames = ["unix_time", "elapsed_s", "policy", "skill_cmd"]
        fieldnames.extend([f"q_{i:02d}_rad" for i in range(self.num_joints)])

        with open(file_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self._rows)

        duration = self._rows[-1]["elapsed_s"]
        print(
            f"[JointCSV] Saved {len(self._rows)} rows, duration={duration:.3f}s, "
            f"path={file_path}"
        )
        self._rows = []
        self._session_tag = ""
        self._start_datetime = None
        return file_path

    def on_policy_step(
        self,
        policy_name,
        trigger_cmd,
        live_cmd,
        joint_positions: Iterable[float],
        session_tag: Optional[str] = None,
    ) -> str:
        """Update logger for one control step.

        Returns file path when a csv is flushed in this step, otherwise empty string.
        """
        if not self.enabled:
            return ""

        policy_name_str = self._name(policy_name)
        trigger_cmd_name = self._name(trigger_cmd)
        live_cmd_name = self._name(live_cmd)
        should_record_policy = self._should_record_policy(policy_name_str)
        start_cmd_name = trigger_cmd_name if trigger_cmd_name != "INVALID" else policy_name_str

        if (not self._active) and should_record_policy:
            self._start(policy_name_str, start_cmd_name, session_tag=session_tag)

        if not self._active:
            return ""

        if self.target_policy_names is not None and (not should_record_policy):
            return self._flush(policy_name_str.lower())

        self._append_row(policy_name_str, live_cmd_name, joint_positions)

        if should_record_policy:
            return ""

        if policy_name_str == "LOCOMODE":
            return self._flush("loco")
        if policy_name_str == "PASSIVE":
            return self._flush("passive")
        if policy_name_str == "FIXEDPOSE":
            return self._flush("fixedpose")
        return ""

    def flush_if_active(self, reason: str) -> str:
        if (not self.enabled) or (not self._active):
            return ""
        return self._flush(reason)
