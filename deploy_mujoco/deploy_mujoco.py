import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.absolute()))
from common.keyboard_joystick import get_joystick

from common.path_config import PROJECT_ROOT

import time
import mujoco.viewer
import mujoco
import numpy as np
import yaml
import os
import re
from common.ctrlcomp import *
from FSM.FSM import *
from common.utils import get_gravity_orientation, FSMCommand, FSMStateName
from common.joystick import JoyStick, JoystickButton

try:
    import imageio.v2 as imageio
    IMAGEIO_AVAILABLE = True
except ImportError:
    imageio = None
    IMAGEIO_AVAILABLE = False



def pd_control(target_q, q, kp, target_dq, dq, kd):
    """Calculates torques from position commands"""
    return (target_q - q) * kp + (target_dq - dq) * kd


class MjVideoRecorder:
    def __init__(self, model, data, sim_dt, recording_cfg):
        self.model = model
        self.data = data
        self.enabled = bool(recording_cfg.get("enabled", False))
        self.auto_start_on_skill = bool(recording_cfg.get("auto_start_on_skill", True))
        self.stop_on_loco = bool(recording_cfg.get("stop_on_loco", True))
        self.output_dir = os.path.join(PROJECT_ROOT, recording_cfg.get("output_dir", "logs/mujoco_videos"))
        self.file_prefix = str(recording_cfg.get("file_prefix", "mujoco_skill")).strip() or "mujoco_skill"
        self.fps = int(recording_cfg.get("fps", 30))
        self.width = int(recording_cfg.get("width", 1280))
        self.height = int(recording_cfg.get("height", 720))

        configured_capture_step = int(recording_cfg.get("capture_every_n_steps", 0))
        auto_capture_step = max(1, int(round(1.0 / max(sim_dt * self.fps, 1e-6))))
        self.capture_every_n_steps = configured_capture_step if configured_capture_step > 0 else auto_capture_step

        self.writer = None
        self.renderer = None
        self.recording = False
        self.frame_counter = 0
        self.current_video_path = ""

        # 跟随相机配置
        follow_cfg = recording_cfg.get("follow_camera", {})
        self.follow_enabled = bool(follow_cfg.get("enabled", True))
        track_body = str(follow_cfg.get("track_body", "pelvis"))
        self.track_body_id = -1
        self.cam = mujoco.MjvCamera()
        self.relative_to_body_yaw = bool(follow_cfg.get("relative_to_body_yaw", True))
        self.azimuth_offset = float(follow_cfg.get("azimuth", 180.0))
        if self.follow_enabled:
            body_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, track_body)
            if body_id < 0:
                print(f"[Recorder] follow_camera: body '{track_body}' not found, falling back to free camera.")
                self.follow_enabled = False
            else:
                self.track_body_id = body_id
                # 使用 FREE 类型，每帧手动更新 lookat 到 body 位置
                # mjCAMERA_TRACKING 需要 mjv_updateCamera 驱动，Python Renderer 不自动调用
                self.cam.type = mujoco.mjtCamera.mjCAMERA_FREE
                self.cam.distance = float(follow_cfg.get("distance", 3.0))
                self.cam.azimuth = self.azimuth_offset
                self.cam.elevation = float(follow_cfg.get("elevation", -20.0))

        if self.enabled and not IMAGEIO_AVAILABLE:
            print("[Recorder] imageio is not available, video recording is disabled.")
            self.enabled = False

    def _safe_name(self, raw_name):
        return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(raw_name)).strip("_") or "skill"

    def start(self, trigger_name):
        if not self.enabled:
            return

        if self.recording:
            self.stop(reason="restart")

        os.makedirs(self.output_dir, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        skill_tag = self._safe_name(trigger_name)
        self.current_video_path = os.path.join(
            self.output_dir,
            f"{self.file_prefix}_{timestamp}_{skill_tag}.mp4",
        )

        try:
            self.renderer = mujoco.Renderer(self.model, height=self.height, width=self.width)
            self.writer = imageio.get_writer(
                self.current_video_path,
                fps=self.fps,
                codec="libx264",
                macro_block_size=None,
            )
            self.recording = True
            self.frame_counter = 0
            print(f"[Recorder] Recording started: {self.current_video_path}")
        except Exception as exc:
            self.recording = False
            self.writer = None
            self.renderer = None
            print(f"[Recorder] Failed to start recording: {exc}")

    def capture(self):
        if not self.recording:
            return

        self.frame_counter += 1
        if self.frame_counter % self.capture_every_n_steps != 0:
            return

        try:
            if self.follow_enabled:
                # 每帧更新 lookat 到 body 的世界坐标，确保相机始终锁定机器人
                self.cam.lookat[:] = self.data.xpos[self.track_body_id]
                if self.relative_to_body_yaw:
                    # xmat 为 body 在世界系的旋转矩阵（row-major）；取 body x 轴投影计算 yaw
                    xmat = self.data.xmat[self.track_body_id]
                    body_yaw_deg = np.degrees(np.arctan2(xmat[3], xmat[0]))
                    self.cam.azimuth = body_yaw_deg + self.azimuth_offset
                self.renderer.update_scene(self.data, camera=self.cam)
            else:
                self.renderer.update_scene(self.data)
            frame = self.renderer.render()
            self.writer.append_data(frame)
        except Exception as exc:
            print(f"[Recorder] Capture failed, stopping recorder: {exc}")
            self.stop(reason="capture_error")

    def stop(self, reason=""):
        if not self.recording and self.writer is None and self.renderer is None:
            return

        video_path = self.current_video_path
        try:
            if self.writer is not None:
                self.writer.close()
        finally:
            self.writer = None
            if self.renderer is not None:
                self.renderer.close()
            self.renderer = None
            was_recording = self.recording
            self.recording = False
            if was_recording:
                suffix = f" (reason: {reason})" if reason else ""
                print(f"[Recorder] Recording saved: {video_path}{suffix}")

if __name__ == "__main__":
    # Wayland 下 GLFW/MuJoCo viewer 的鼠标拖拽/点击有时会异常；
    # 若用户显式要求 X11，则尽量让 GLFW 与 SDL 都走 X11/XWayland。
    if os.getenv("GLFW_PLATFORM", "").lower() == "x11":
        # SDL/pygame 也切到 X11（避免 Wayland/SDL 与 X11/GLFW 混用导致输入异常）
        os.environ.setdefault("SDL_VIDEODRIVER", "x11")
        # 在 Wayland 会话里，只要有 DISPLAY（XWayland）就移除 WAYLAND_DISPLAY，逼迫 GLFW 选择 X11
        if os.getenv("DISPLAY") and os.getenv("WAYLAND_DISPLAY"):
            os.environ.pop("WAYLAND_DISPLAY", None)

    current_dir = os.path.dirname(os.path.abspath(__file__))
    mujoco_yaml_path = os.path.join(current_dir, "config", "mujoco.yaml")
    with open(mujoco_yaml_path, "r") as f:
        config = yaml.load(f, Loader=yaml.FullLoader)
        xml_path = os.path.join(PROJECT_ROOT, config["xml_path"])
        simulation_dt = config["simulation_dt"]
        control_decimation = config["control_decimation"]
        recording_cfg = config.get("recording", {})
        
    m = mujoco.MjModel.from_xml_path(xml_path)
    d = mujoco.MjData(m)
    m.opt.timestep = simulation_dt
    mj_per_step_duration = simulation_dt * control_decimation
    num_joints = m.nu
    policy_output_action = np.zeros(num_joints, dtype=np.float32)
    kps = np.zeros(num_joints, dtype=np.float32)
    kds = np.zeros(num_joints, dtype=np.float32)
    sim_counter = 0
    
    state_cmd = StateAndCmd(num_joints)
    policy_output = PolicyOutput(num_joints)
    FSM_controller = FSM(state_cmd, policy_output)
    recorder = MjVideoRecorder(m, d, simulation_dt, recording_cfg)
    
    joystick = get_joystick()
    # 提示：Wayland 下 MuJoCo viewer 的鼠标按钮可能失效，提供键盘/手柄快捷键
    print('提示: Enter(或手柄 START)=姿态复位到默认位姿(FixedPose)；R(或手柄 R3，或键盘 F5/V)=MuJoCo 硬重置并回到 LOCO(重新放置机器人)')
    print('快捷键: Shift+X=SKILL_1，Shift+Y=SKILL_2，Shift+B=SKILL_3/WBT_DANCE，Tab+Y=SKILL_4/WBT_DANCE，Tab+T=BeyondMimic')
    Running = True
    with mujoco.viewer.launch_passive(m, d) as viewer:
        sim_start_time = time.time()
        while viewer.is_running() and Running:
            step_start = time.time()
            try:
                # 必须先更新输入状态
                joystick.update()
                triggered_skill_name = ""

                # MuJoCo 仿真硬重置：回到 XML 的初始 qpos/qvel（相当于“重新放置机器人”）
                # - 键盘：F5（在 keyboard_joystick.py 映射为 R3）
                # - 手柄：R3
                if joystick.is_button_just_pressed(JoystickButton.R3):
                    mujoco.mj_resetData(m, d)
                    mujoco.mj_forward(m, d)
                    sim_counter = 0
                    policy_output_action[:] = 0.0
                    kps[:] = 0.0
                    kds[:] = 0.0
                    state_cmd.vel_cmd[:] = 0.0
                    state_cmd.skill_cmd = FSMCommand.LOCO
                    recorder.stop(reason="hard_reset")
                    print('>>> MuJoCo 硬重置完成：已重新放置机器人，并切回 LOCO')
                
                # 终止程序（按下 SELECT）
                if joystick.is_button_just_pressed(JoystickButton.SELECT):
                    Running = False
                    recorder.stop(reason="program_exit")

                # 更灵敏的触发：使用按下边缘 (just_pressed)
                if joystick.is_button_just_pressed(JoystickButton.L3):
                    state_cmd.skill_cmd = FSMCommand.PASSIVE
                    print(">>> 切换到: PASSIVE 阻尼保护模式")
                if joystick.is_button_just_pressed(JoystickButton.START):
                    state_cmd.skill_cmd = FSMCommand.POS_RESET
                    print(">>> 切换到: POS_RESET 位控模式")

                # LOCO: R1 + A
                if joystick.is_button_just_pressed(JoystickButton.A) and joystick.is_button_pressed(JoystickButton.R1):
                    state_cmd.skill_cmd = FSMCommand.LOCO
                    print(">>> 切换到: LOCO 行走模式")

                # SKILL_1 (Dance): R1 + X
                if joystick.is_button_just_pressed(JoystickButton.X) and joystick.is_button_pressed(JoystickButton.R1):
                    # 如果当前就是 Dance，则重启该策略；否则发起切换
                    if FSM_controller.cur_policy.name == FSMStateName.SKILL_Dance:
                        FSM_controller.cur_policy.exit()
                        FSM_controller.cur_policy.enter()
                        triggered_skill_name = "SKILL_1_Dance"
                        print(">>> 重新启动: SKILL_1 舞蹈模式")
                    else:
                        state_cmd.skill_cmd = FSMCommand.SKILL_1
                        triggered_skill_name = "SKILL_1_Dance"
                        print(">>> 切换到: SKILL_1 舞蹈模式")

                # SKILL_2 (KungFu): R1 + Y
                if joystick.is_button_just_pressed(JoystickButton.Y) and joystick.is_button_pressed(JoystickButton.R1):
                    if FSM_controller.cur_policy.name == FSMStateName.SKILL_KungFu:
                        FSM_controller.cur_policy.exit()
                        FSM_controller.cur_policy.enter()
                        triggered_skill_name = "SKILL_2_KungFu"
                        print(">>> 重新启动: SKILL_2 武术模式")
                    else:
                        state_cmd.skill_cmd = FSMCommand.SKILL_2
                        triggered_skill_name = "SKILL_2_KungFu"
                        print(">>> 切换到: SKILL_2 武术模式")

                # SKILL_3 (WBT_DANCE/Kick): R1 + B
                if joystick.is_button_just_pressed(JoystickButton.B) and joystick.is_button_pressed(JoystickButton.R1):
                    if FSM_controller.cur_policy.name == FSMStateName.SKILL_WBT_DANCE:
                        FSM_controller.cur_policy.exit()
                        FSM_controller.cur_policy.enter()
                        triggered_skill_name = "SKILL_3_WBT_DANCE"
                        print(">>> 重新启动: SKILL_3 WBT_DANCE")
                    else:
                        state_cmd.skill_cmd = FSMCommand.SKILL_3
                        triggered_skill_name = "SKILL_3_WBT_DANCE"
                        print(">>> 切换到: SKILL_3 WBT_DANCE (whole_body_tracking 导出策略)")

                # SKILL_4 (WBT_DANCE variant): L1 + Y
                if joystick.is_button_just_pressed(JoystickButton.Y) and joystick.is_button_pressed(JoystickButton.L1):
                    if FSM_controller.cur_policy.name == FSMStateName.SKILL_WBT_DANCE:
                        FSM_controller.cur_policy.exit()
                        FSM_controller.cur_policy.enter()
                        triggered_skill_name = "SKILL_4_WBT_DANCE"
                        print(">>> 重新启动: SKILL_4 WBT_DANCE")
                    else:
                        state_cmd.skill_cmd = FSMCommand.SKILL_4
                        triggered_skill_name = "SKILL_4_WBT_DANCE"
                        print(">>> 切换到: SKILL_4 WBT_DANCE (whole_body_tracking 导出策略)")

                # SKILL_5 (BeyondMimic): L1 + HOME / 键盘 Tab + T
                if joystick.is_button_just_pressed(JoystickButton.HOME) and joystick.is_button_pressed(JoystickButton.L1):
                    if FSM_controller.cur_policy.name == FSMStateName.SKILL_BEYOND_MIMIC:
                        FSM_controller.cur_policy.exit()
                        FSM_controller.cur_policy.enter()
                        triggered_skill_name = "SKILL_5_BeyondMimic"
                        print(">>> 重新启动: SKILL_5 BeyondMimic")
                    else:
                        state_cmd.skill_cmd = FSMCommand.SKILL_5
                        triggered_skill_name = "SKILL_5_BeyondMimic"
                        print(">>> 切换到: SKILL_5 BeyondMimic (walking ONNX)")

                if recorder.auto_start_on_skill and triggered_skill_name:
                    recorder.start(triggered_skill_name)
                
                state_cmd.vel_cmd[0] = -joystick.get_axis_value(1)
                state_cmd.vel_cmd[1] = -joystick.get_axis_value(0)
                state_cmd.vel_cmd[2] = -joystick.get_axis_value(3)
                
                tau = pd_control(policy_output_action, d.qpos[7:], kps, np.zeros_like(kps), d.qvel[6:], kds)
                d.ctrl[:] = tau
                mujoco.mj_step(m, d)
                recorder.capture()
                sim_counter += 1
                if sim_counter % control_decimation == 0:
                    prev_policy_name = FSM_controller.cur_policy.name
                    
                    qj = d.qpos[7:]
                    dqj = d.qvel[6:]
                    quat = d.qpos[3:7]
                    
                    omega = d.qvel[3:6] 
                    gravity_orientation = get_gravity_orientation(quat)
                    
                    state_cmd.q = qj.copy()
                    state_cmd.dq = dqj.copy()
                    state_cmd.gravity_ori = gravity_orientation.copy()
                    state_cmd.base_quat = quat.copy()
                    state_cmd.ang_vel = omega.copy()
                    
                    FSM_controller.run()

                    if (
                        recorder.recording
                        and recorder.stop_on_loco
                        and prev_policy_name != FSMStateName.LOCOMODE
                        and FSM_controller.cur_policy.name == FSMStateName.LOCOMODE
                    ):
                        recorder.stop(reason="entered_loco")

                    policy_output_action = policy_output.actions.copy()
                    kps = policy_output.kps.copy()
                    kds = policy_output.kds.copy()
            except ValueError as e:
                print(str(e))
            
            # 仅在控制步刷新 viewer，避免以 333 Hz 渲染拖慢实时率
            if sim_counter % control_decimation == 0:
                viewer.sync()
            time_until_next_step = m.opt.timestep - (time.time() - step_start)
            if time_until_next_step > 0:
                time.sleep(time_until_next_step)

        recorder.stop(reason="viewer_closed")
        