from __future__ import annotations

import os
from dataclasses import dataclass

import numpy as np
import onnx
import onnxruntime
import torch
import yaml

from FSM.FSMState import FSMState, FSMStateName
from common.ctrlcomp import PolicyOutput, StateAndCmd
from common.utils import FSMCommand


@dataclass
class _FallbackParams:
    default_joint_pos: np.ndarray
    joint_stiffness: np.ndarray
    joint_damping: np.ndarray
    action_scale: np.ndarray


def _parse_csv_list(raw: str) -> list[str]:
    # exporter.py 写入的是逗号分隔字符串
    # 这里做一个温和的解析（去空格、过滤空项）
    return [x.strip() for x in str(raw).split(",") if x.strip()]


def _parse_float_list(raw: str) -> np.ndarray:
    parts = _parse_csv_list(raw)
    return np.array([float(x) for x in parts], dtype=np.float32)


class WbtDance(FSMState):
    """whole_body_tracking 导出的 motion-tracking ONNX 策略（sim2sim）。

    适配任务: Tracking-Flat-G1-Wo-State-Estimation-v0
    观测结构与 `policy/beyond_mimic/BeyondMimic.py` 保持一致：
      [ref_joint_pos(29), ref_joint_vel(29), motion_anchor_ori_b(6), base_ang_vel(3),
       joint_pos_rel(29), joint_vel_rel(29), last_action(29)] -> 154

    ONNX 期望输入: (obs, time_step)
    ONNX 输出: (actions, joint_pos, joint_vel, body_pos_w, body_quat_w, body_lin_vel_w, body_ang_vel_w)
    """

    def __init__(self, state_cmd: StateAndCmd, policy_output: PolicyOutput):
        super().__init__()
        self.state_cmd = state_cmd
        self.policy_output = policy_output
        self.name = FSMStateName.SKILL_WBT_DANCE
        self.name_str = "wbt_dance"

        current_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(current_dir, "config", "WbtDance.yaml")
        with open(config_path, "r") as f:
            config = yaml.load(f, Loader=yaml.FullLoader)

        self.onnx_path = os.path.join(current_dir, "model", config["onnx_path"])
        self.mj2lab = np.array(config["mj2lab"], dtype=np.int32)
        self.use_onnx_metadata = bool(config.get("use_onnx_metadata", True))

        fb = config.get("fallback", {})
        self.fallback = _FallbackParams(
            default_joint_pos=np.array(fb.get("default_joint_pos", [0.0] * 29), dtype=np.float32),
            joint_stiffness=np.array(fb.get("joint_stiffness", [20.0] * 29), dtype=np.float32),
            joint_damping=np.array(fb.get("joint_damping", [1.0] * 29), dtype=np.float32),
            action_scale=np.array(fb.get("action_scale", [0.25] * 29), dtype=np.float32),
        )

        # runtime states
        self.counter_step = 0
        self.action = np.zeros((1, 29), dtype=np.float32)
        self.ref_joint_pos = np.zeros((1, 29), dtype=np.float32)
        self.ref_joint_vel = np.zeros((1, 29), dtype=np.float32)
        self.ref_body_quat_w = np.zeros((1, 14, 4), dtype=np.float32)

        # load policy
        if not os.path.exists(self.onnx_path):
            raise FileNotFoundError(f"ONNX not found: {self.onnx_path}")

        self.onnx_model = onnx.load(self.onnx_path)
        self.ort_session = onnxruntime.InferenceSession(self.onnx_path)
        self.input_names = [i.name for i in self.ort_session.get_inputs()]

        # infer obs dim
        obs_shape = self.ort_session.get_inputs()[0].shape
        # expect [1, N]
        self.num_obs = int(obs_shape[1]) if len(obs_shape) >= 2 and obs_shape[1] is not None else 154

        self._load_params_from_metadata_or_fallback()

        print(f"WbtDance policy initializing ... onnx={os.path.basename(self.onnx_path)} obs_dim={self.num_obs}")

    def _load_params_from_metadata_or_fallback(self) -> None:
        if not self.use_onnx_metadata:
            self._use_fallback()
            return

        meta = {p.key: p.value for p in self.onnx_model.metadata_props}
        try:
            default_joint_pos = _parse_float_list(meta["default_joint_pos"])
            joint_stiffness = _parse_float_list(meta["joint_stiffness"])
            joint_damping = _parse_float_list(meta["joint_damping"])
            action_scale = _parse_float_list(meta["action_scale"])

            if len(default_joint_pos) != 29 or len(joint_stiffness) != 29 or len(joint_damping) != 29 or len(action_scale) != 29:
                raise ValueError("metadata list length mismatch")

            self.default_angles_lab = default_joint_pos.astype(np.float32)
            self.kps_lab = joint_stiffness.astype(np.float32)
            self.kds_lab = joint_damping.astype(np.float32)
            self.action_scale_lab = action_scale.astype(np.float32)
            return
        except Exception:
            self._use_fallback()

    def _use_fallback(self) -> None:
        self.default_angles_lab = self.fallback.default_joint_pos
        self.kps_lab = self.fallback.joint_stiffness
        self.kds_lab = self.fallback.joint_damping
        self.action_scale_lab = self.fallback.action_scale

    def enter(self):
        self.counter_step = 0

        # warmup one step to fetch ref motion outputs
        observation = {
            self.input_names[0]: np.zeros((1, self.num_obs), dtype=np.float32),
            self.input_names[1]: np.zeros((1, 1), dtype=np.float32),
        }
        outputs = self.ort_session.run(None, observation)
        self.action, self.ref_joint_pos, self.ref_joint_vel, _, self.ref_body_quat_w, _, _ = outputs

        # reorder kp/kd into mujoco motor order
        self.kps_reorder = np.zeros(29, dtype=np.float32)
        self.kds_reorder = np.zeros(29, dtype=np.float32)
        self.default_angles_reorder = np.zeros(29, dtype=np.float32)
        for lab_idx, mj_idx in enumerate(self.mj2lab):
            self.kps_reorder[mj_idx] = self.kps_lab[lab_idx]
            self.kds_reorder[mj_idx] = self.kds_lab[lab_idx]
            self.default_angles_reorder[mj_idx] = self.default_angles_lab[lab_idx]

        # yaw alignment cache
        self.init_to_world = None

    def quat_mul(self, q1, q2):
        w1, x1, y1, z1 = q1[0], q1[1], q1[2], q1[3]
        w2, x2, y2, z2 = q2[0], q2[1], q2[2], q2[3]
        ww = (z1 + x1) * (x2 + y2)
        yy = (w1 - y1) * (w2 + z2)
        zz = (w1 + y1) * (w2 - x2)
        xx = ww + yy + zz
        qq = 0.5 * (xx + (z1 - x1) * (x2 - y2))
        w = qq - ww + (z1 - y1) * (y2 - z2)
        x = qq - xx + (x1 + w1) * (x2 + w2)
        y = qq - yy + (w1 - x1) * (y2 + z2)
        z = qq - zz + (z1 + y1) * (w2 - x2)
        return np.array([w, x, y, z])

    def matrix_from_quat(self, q):
        w, x, y, z = q
        return np.array(
            [
                [1 - 2 * (y**2 + z**2), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                [2 * (x * y + z * w), 1 - 2 * (x**2 + z**2), 2 * (y * z - x * w)],
                [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x**2 + y**2)],
            ]
        )

    def yaw_quat(self, q):
        w, x, y, z = q
        yaw = np.arctan2(2 * (w * z + x * y), 1 - 2 * (y**2 + z**2))
        return np.array([np.cos(yaw / 2), 0, 0, np.sin(yaw / 2)])

    def euler_single_axis_to_quat(self, angle, axis, degrees=False):
        if degrees:
            angle = np.radians(angle)
        half_angle = angle * 0.5
        cos_half = np.cos(half_angle)
        sin_half = np.sin(half_angle)
        if axis.lower() == "x":
            return np.array([cos_half, sin_half, 0.0, 0.0])
        if axis.lower() == "y":
            return np.array([cos_half, 0.0, sin_half, 0.0])
        if axis.lower() == "z":
            return np.array([cos_half, 0.0, 0.0, sin_half])
        raise ValueError("axis must be 'x', 'y', or 'z'")

    def run(self):
        # robot base quat from mujoco
        robot_quat = self.state_cmd.base_quat

        # joint pos/vel (mujoco) -> lab order, and relative to default
        qj_lab = (self.state_cmd.q[self.mj2lab] - self.default_angles_lab)
        dqj_lab = self.state_cmd.dq[self.mj2lab]

        # pelvis->torso adjustment (keep aligned with existing BeyondMimic impl)
        base_troso_yaw = qj_lab[2]
        base_troso_roll = qj_lab[5]
        base_troso_pitch = qj_lab[8]

        quat_yaw = self.euler_single_axis_to_quat(base_troso_yaw, "z", degrees=False)
        quat_roll = self.euler_single_axis_to_quat(base_troso_roll, "x", degrees=False)
        quat_pitch = self.euler_single_axis_to_quat(base_troso_pitch, "y", degrees=False)
        robot_quat = self.quat_mul(robot_quat, self.quat_mul(quat_yaw, self.quat_mul(quat_roll, quat_pitch)))

        ref_anchor_ori_w = self.ref_body_quat_w[:, 7].squeeze(0)

        # first frames: compute yaw alignment
        if self.counter_step < 2:
            init_to_anchor = self.matrix_from_quat(self.yaw_quat(ref_anchor_ori_w))
            world_to_anchor = self.matrix_from_quat(self.yaw_quat(robot_quat))
            self.init_to_world = world_to_anchor @ init_to_anchor.T
            self.counter_step += 1
            return

        motion_anchor_ori_b = self.matrix_from_quat(robot_quat).T @ self.init_to_world @ self.matrix_from_quat(ref_anchor_ori_w)

        base_ang_vel = self.state_cmd.ang_vel

        # build obs (Tracking-Flat-G1-Wo-State-Estimation-v0)
        obs_buf = np.concatenate(
            (
                self.ref_joint_pos.squeeze(0),
                self.ref_joint_vel.squeeze(0),
                motion_anchor_ori_b[:, :2].reshape(-1),
                base_ang_vel,
                qj_lab,
                dqj_lab,
                self.action.squeeze(0),
            ),
            axis=-1,
            dtype=np.float32,
        )

        observation = {
            self.input_names[0]: torch.from_numpy(obs_buf).unsqueeze(0).cpu().numpy(),
            self.input_names[1]: np.array([[self.counter_step]], dtype=np.float32),
        }

        outputs = self.ort_session.run(None, observation)
        self.action, self.ref_joint_pos, self.ref_joint_vel, _, self.ref_body_quat_w, _, _ = outputs

        # action (lab) -> target dof pos (mujoco order)
        target_dof_pos_lab = self.action * self.action_scale_lab + self.default_angles_lab
        target_dof_pos_mj = np.zeros(29, dtype=np.float32)
        target_dof_pos_mj[self.mj2lab] = target_dof_pos_lab.squeeze(0)

        self.policy_output.actions = target_dof_pos_mj
        self.policy_output.kps = self.kps_reorder
        self.policy_output.kds = self.kds_reorder

        self.counter_step += 1

    def exit(self):
        self.counter_step = 0
        self.action = np.zeros((1, 29), dtype=np.float32)
        print("WbtDance exited")

    def checkChange(self):
        # return back to safe modes
        if self.state_cmd.skill_cmd == FSMCommand.LOCO:
            self.state_cmd.skill_cmd = FSMCommand.INVALID
            return FSMStateName.SKILL_COOLDOWN
        if self.state_cmd.skill_cmd == FSMCommand.PASSIVE:
            self.state_cmd.skill_cmd = FSMCommand.INVALID
            return FSMStateName.PASSIVE
        if self.state_cmd.skill_cmd == FSMCommand.POS_RESET:
            self.state_cmd.skill_cmd = FSMCommand.INVALID
            return FSMStateName.FIXEDPOSE

        self.state_cmd.skill_cmd = FSMCommand.INVALID
        return FSMStateName.SKILL_WBT_DANCE
