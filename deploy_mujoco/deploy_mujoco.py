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
    Running = True
    with mujoco.viewer.launch_passive(m, d) as viewer:
        sim_start_time = time.time()
        while viewer.is_running() and Running:
            step_start = time.time()
            try:
                # 必须先更新输入状态
                joystick.update()
                
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
        