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
from common.ctrlcomp import *
from FSM.FSM import *
from common.utils import get_gravity_orientation, FSMCommand, FSMStateName
from common.joystick import JoyStick, JoystickButton



def pd_control(target_q, q, kp, target_dq, dq, kd):
    """Calculates torques from position commands"""
    return (target_q - q) * kp + (target_dq - dq) * kd

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
    
    joystick = get_joystick()
    # 提示：Wayland 下 MuJoCo viewer 的鼠标按钮可能失效，提供键盘/手柄快捷键
    print('提示: Enter(或手柄 START)=姿态复位到默认位姿(FixedPose)；R(或手柄 R3，或键盘 F5/V)=MuJoCo 硬重置并回到 LOCO(重新放置机器人)')
    Running = True
    with mujoco.viewer.launch_passive(m, d) as viewer:
        sim_start_time = time.time()
        while viewer.is_running() and Running:
            step_start = time.time()
            try:
                # 必须先更新输入状态
                joystick.update()

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
                    print('>>> MuJoCo 硬重置完成：已重新放置机器人，并切回 LOCO')
                
                # 终止程序（按下 SELECT）
                if joystick.is_button_just_pressed(JoystickButton.SELECT):
                    Running = False

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
                        print(">>> 重新启动: SKILL_1 舞蹈模式")
                    else:
                        state_cmd.skill_cmd = FSMCommand.SKILL_1
                        print(">>> 切换到: SKILL_1 舞蹈模式")

                # SKILL_2 (KungFu): R1 + Y
                if joystick.is_button_just_pressed(JoystickButton.Y) and joystick.is_button_pressed(JoystickButton.R1):
                    if FSM_controller.cur_policy.name == FSMStateName.SKILL_KungFu:
                        FSM_controller.cur_policy.exit()
                        FSM_controller.cur_policy.enter()
                        print(">>> 重新启动: SKILL_2 武术模式")
                    else:
                        state_cmd.skill_cmd = FSMCommand.SKILL_2
                        print(">>> 切换到: SKILL_2 武术模式")

                # SKILL_3 (WBT_DANCE/Kick): R1 + B
                if joystick.is_button_just_pressed(JoystickButton.B) and joystick.is_button_pressed(JoystickButton.R1):
                    if FSM_controller.cur_policy.name == FSMStateName.SKILL_WBT_DANCE:
                        FSM_controller.cur_policy.exit()
                        FSM_controller.cur_policy.enter()
                        print(">>> 重新启动: SKILL_3 WBT_DANCE")
                    else:
                        state_cmd.skill_cmd = FSMCommand.SKILL_3
                        print(">>> 切换到: SKILL_3 WBT_DANCE (whole_body_tracking 导出策略)")

                # SKILL_4 (WBT_DANCE variant): L1 + Y
                if joystick.is_button_just_pressed(JoystickButton.Y) and joystick.is_button_pressed(JoystickButton.L1):
                    if FSM_controller.cur_policy.name == FSMStateName.SKILL_WBT_DANCE:
                        FSM_controller.cur_policy.exit()
                        FSM_controller.cur_policy.enter()
                        print(">>> 重新启动: SKILL_4 WBT_DANCE")
                    else:
                        state_cmd.skill_cmd = FSMCommand.SKILL_4
                        print(">>> 切换到: SKILL_4 WBT_DANCE (whole_body_tracking 导出策略)")
                
                state_cmd.vel_cmd[0] = -joystick.get_axis_value(1)
                state_cmd.vel_cmd[1] = -joystick.get_axis_value(0)
                state_cmd.vel_cmd[2] = -joystick.get_axis_value(3)
                
                tau = pd_control(policy_output_action, d.qpos[7:], kps, np.zeros_like(kps), d.qvel[6:], kds)
                d.ctrl[:] = tau
                mujoco.mj_step(m, d)
                sim_counter += 1
                if sim_counter % control_decimation == 0:
                    
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
                    policy_output_action = policy_output.actions.copy()
                    kps = policy_output.kps.copy()
                    kds = policy_output.kds.copy()
            except ValueError as e:
                print(str(e))
            
            viewer.sync()
            time_until_next_step = m.opt.timestep - (time.time() - step_start)
            if time_until_next_step > 0:
                time.sleep(time_until_next_step)
        