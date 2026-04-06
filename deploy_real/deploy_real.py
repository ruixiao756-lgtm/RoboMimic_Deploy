import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.absolute()))

from common.path_config import PROJECT_ROOT
from common.ctrlcomp import *
from FSM.FSM import *
from typing import Union
import numpy as np
import time
import os
import yaml
import csv
from datetime import datetime

from unitree_sdk2py.core.channel import ChannelPublisher, ChannelFactoryInitialize
from unitree_sdk2py.core.channel import ChannelSubscriber, ChannelFactoryInitialize
from unitree_sdk2py.idl.default import unitree_hg_msg_dds__LowCmd_, unitree_hg_msg_dds__LowState_
from unitree_sdk2py.idl.default import unitree_go_msg_dds__LowCmd_, unitree_go_msg_dds__LowState_
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowCmd_ as LowCmdHG
from unitree_sdk2py.idl.unitree_go.msg.dds_ import LowCmd_ as LowCmdGo
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowState_ as LowStateHG
from unitree_sdk2py.idl.unitree_go.msg.dds_ import LowState_ as LowStateGo
from unitree_sdk2py.utils.crc import CRC

from common.command_helper import create_damping_cmd, create_zero_cmd, init_cmd_hg, init_cmd_go, MotorMode
from common.rotation_helper import get_gravity_orientation_real, transform_imu_data
from common.remote_controller import RemoteController, KeyMap
from config import Config


class Controller:
    def __init__(self, config: Config):
        self.config = config
        self.remote_controller = RemoteController()
        self.num_joints = config.num_joints
        self.control_dt = config.control_dt
        
        
        self.low_cmd = unitree_hg_msg_dds__LowCmd_()
        self.low_state = unitree_hg_msg_dds__LowState_()
        self.mode_pr_ = MotorMode.PR
        self.mode_machine_ = 0
        self.lowcmd_publisher_ = ChannelPublisher(config.lowcmd_topic, LowCmdHG)
        self.lowcmd_publisher_.Init()
        
        # inital connection
        self.lowstate_subscriber = ChannelSubscriber(config.lowstate_topic, LowStateHG)
        self.lowstate_subscriber.Init(self.LowStateHgHandler, 10)
        
        self.wait_for_low_state()
        
        init_cmd_hg(self.low_cmd, self.mode_machine_, self.mode_pr_)
        
        self.policy_output_action = np.zeros(self.num_joints, dtype=np.float32)
        self.kps = np.zeros(self.num_joints, dtype=np.float32)
        self.kds = np.zeros(self.num_joints, dtype=np.float32)
        self.qj = np.zeros(self.num_joints, dtype=np.float32)
        self.dqj = np.zeros(self.num_joints, dtype=np.float32)
        self.quat = np.zeros(4, dtype=np.float32)
        self.ang_vel = np.zeros(3, dtype=np.float32)
        self.gravity_orientation = np.array([0,0,-1], dtype=np.float32)
        
        self.state_cmd = StateAndCmd(self.num_joints)
        self.policy_output = PolicyOutput(self.num_joints)
        self.FSM_controller = FSM(self.state_cmd, self.policy_output)
        
        self.running = True
        self.counter_over_time = 0

        # Joint-angle logging during one skill execution window.
        self.joint_csv_log_enabled = bool(config.joint_csv_log_enabled)
        self.joint_csv_log_dir = config.joint_csv_log_dir
        if not os.path.isabs(self.joint_csv_log_dir):
            self.joint_csv_log_dir = os.path.join(PROJECT_ROOT, self.joint_csv_log_dir)
        self.joint_csv_log_sample_stride = max(1, int(config.joint_csv_log_sample_stride))
        self._joint_log_active = False
        self._joint_log_rows = []
        self._joint_log_start_time = 0.0
        self._joint_log_start_policy = ""
        self._joint_log_start_cmd = ""
        self._joint_log_episode_id = 0
        self._joint_log_loop_idx = 0
        if self.joint_csv_log_enabled:
            os.makedirs(self.joint_csv_log_dir, exist_ok=True)
            print(f"[JointCSV] Enabled. Output dir: {self.joint_csv_log_dir}")

    def _is_skill_policy(self, policy_name: FSMStateName) -> bool:
        return policy_name.name.startswith("SKILL_")

    def _start_joint_log(self, policy_name: FSMStateName, trigger_cmd: FSMCommand):
        self._joint_log_active = True
        self._joint_log_rows = []
        self._joint_log_start_time = time.time()
        self._joint_log_start_policy = policy_name.name
        self._joint_log_start_cmd = trigger_cmd.name
        self._joint_log_loop_idx = 0
        print(f"[JointCSV] Start recording from policy={self._joint_log_start_policy}, cmd={self._joint_log_start_cmd}")

    def _append_joint_log_row(self, policy_name: FSMStateName, live_cmd: FSMCommand):
        if not self._joint_log_active:
            return

        if (self._joint_log_loop_idx % self.joint_csv_log_sample_stride) != 0:
            self._joint_log_loop_idx += 1
            return

        now = time.time()
        row = {
            "unix_time": now,
            "elapsed_s": now - self._joint_log_start_time,
            "policy": policy_name.name,
            "skill_cmd": live_cmd.name,
        }
        for i in range(self.num_joints):
            row[f"q_{i:02d}_rad"] = float(self.qj[i])
        self._joint_log_rows.append(row)
        self._joint_log_loop_idx += 1

    def _flush_joint_log(self, reason: str):
        if not self._joint_log_active:
            return

        self._joint_log_active = False
        if len(self._joint_log_rows) == 0:
            print(f"[JointCSV] No samples collected, skip file write. reason={reason}")
            return

        self._joint_log_episode_id += 1
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = (
            f"joint_log_{ts}_ep{self._joint_log_episode_id:03d}_"
            f"{self._joint_log_start_policy}_{self._joint_log_start_cmd}_to_{reason}.csv"
        )
        file_path = os.path.join(self.joint_csv_log_dir, file_name)

        fieldnames = ["unix_time", "elapsed_s", "policy", "skill_cmd"]
        fieldnames.extend([f"q_{i:02d}_rad" for i in range(self.num_joints)])

        with open(file_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self._joint_log_rows)

        duration = self._joint_log_rows[-1]["elapsed_s"]
        print(
            f"[JointCSV] Saved {len(self._joint_log_rows)} rows, duration={duration:.3f}s, "
            f"path={file_path}"
        )
        self._joint_log_rows = []
        
        
    def LowStateHgHandler(self, msg: LowStateHG):
        self.low_state = msg
        self.mode_machine_ = self.low_state.mode_machine
        self.remote_controller.set(self.low_state.wireless_remote)

    def LowStateGoHandler(self, msg: LowStateGo):
        self.low_state = msg
        self.remote_controller.set(self.low_state.wireless_remote)

    def send_cmd(self, cmd: Union[LowCmdGo, LowCmdHG]):
        cmd.crc = CRC().Crc(cmd)
        self.lowcmd_publisher_.Write(cmd)

    def wait_for_low_state(self):
        while self.low_state.tick == 0:
            time.sleep(self.config.control_dt)
        print("Successfully connected to the robot.")

    def zero_torque_state(self):
        print("Enter zero torque state.")
        print("Waiting for the start signal...")
        while self.remote_controller.button[KeyMap.start] != 1:
            create_zero_cmd(self.low_cmd)
            self.send_cmd(self.low_cmd)
            time.sleep(self.config.control_dt)
        
    def run(self):
        try:
            if(self.counter_over_time >= self.config.error_over_time):
                print(f"[SAFETY] Control loop over time {self.counter_over_time} times, switching to PASSIVE.")
                self.state_cmd.skill_cmd = FSMCommand.PASSIVE
                self.counter_over_time = 0
            
            loop_start_time = time.time()
            
            if self.remote_controller.is_button_pressed(KeyMap.F1):
                self.state_cmd.skill_cmd = FSMCommand.PASSIVE
            if self.remote_controller.is_button_pressed(KeyMap.start):
                self.state_cmd.skill_cmd = FSMCommand.POS_RESET
            if self.remote_controller.is_button_pressed(KeyMap.A) and self.remote_controller.is_button_pressed(KeyMap.R1):
                self.state_cmd.skill_cmd = FSMCommand.LOCO
            if self.remote_controller.is_button_pressed(KeyMap.X) and self.remote_controller.is_button_pressed(KeyMap.R1):
                self.state_cmd.skill_cmd = FSMCommand.SKILL_1
            if self.remote_controller.is_button_pressed(KeyMap.Y) and self.remote_controller.is_button_pressed(KeyMap.R1):
                self.state_cmd.skill_cmd = FSMCommand.SKILL_2
            if self.remote_controller.is_button_pressed(KeyMap.B) and self.remote_controller.is_button_pressed(KeyMap.R1):
                if self.FSM_controller.cur_policy.name == FSMStateName.SKILL_BEYOND_MIMIC:
                    # 已在 BeyondMimic：直接重启（触发 _reload_config 热重载）
                    self.FSM_controller.cur_policy.exit()
                    self.FSM_controller.cur_policy.enter()
                    print("[BeyondMimic] Restarted (hot-reload config/ONNX)")
                else:
                    self.state_cmd.skill_cmd = FSMCommand.SKILL_5  # BeyondMimic
            if self.remote_controller.is_button_pressed(KeyMap.Y) and self.remote_controller.is_button_pressed(KeyMap.L1):
                self.state_cmd.skill_cmd = FSMCommand.SKILL_4  # WbtDance
            
            self.state_cmd.vel_cmd[0] =  self.remote_controller.ly
            self.state_cmd.vel_cmd[1] =  self.remote_controller.lx * -1
            self.state_cmd.vel_cmd[2] =  self.remote_controller.rx * -1
            trigger_cmd = self.state_cmd.skill_cmd

            for i in range(self.num_joints):
                self.qj[i] = self.low_state.motor_state[i].q
                self.dqj[i] = self.low_state.motor_state[i].dq

            # imu_state quaternion: w, x, y, z
            quat = self.low_state.imu_state.quaternion
            ang_vel = np.array(self.low_state.imu_state.gyroscope, dtype=np.float32)
            
            gravity_orientation = get_gravity_orientation_real(quat)
            
            self.state_cmd.q = self.qj.copy()
            self.state_cmd.dq = self.dqj.copy()
            self.state_cmd.gravity_ori = gravity_orientation.copy()
            self.state_cmd.ang_vel = ang_vel.copy()
            self.state_cmd.base_quat = quat
            
            self.FSM_controller.run()
            cur_policy_name = self.FSM_controller.cur_policy.name

            if self.joint_csv_log_enabled:
                if (not self._joint_log_active) and self._is_skill_policy(cur_policy_name):
                    self._start_joint_log(cur_policy_name, trigger_cmd)

                if self._joint_log_active:
                    self._append_joint_log_row(cur_policy_name, self.state_cmd.skill_cmd)

                    if not self._is_skill_policy(cur_policy_name):
                        if cur_policy_name == FSMStateName.LOCOMODE:
                            self._flush_joint_log("loco")
                        elif cur_policy_name == FSMStateName.PASSIVE:
                            self._flush_joint_log("passive")
                        elif cur_policy_name == FSMStateName.FIXEDPOSE:
                            self._flush_joint_log("fixedpose")

            policy_output_action = self.policy_output.actions.copy()
            kps = self.policy_output.kps.copy()
            kds = self.policy_output.kds.copy()
            
            # Build low cmd
            for i in range(self.num_joints):
                self.low_cmd.motor_cmd[i].q = policy_output_action[i]
                self.low_cmd.motor_cmd[i].qd = 0
                self.low_cmd.motor_cmd[i].kp = kps[i]
                self.low_cmd.motor_cmd[i].kd = kds[i]
                self.low_cmd.motor_cmd[i].tau = 0
                
            # send the command
            # create_damping_cmd(controller.low_cmd) # only for debug
            self.send_cmd(self.low_cmd)
            
            loop_end_time = time.time()
            delta_time = loop_end_time - loop_start_time
            if(delta_time < self.control_dt):
                time.sleep(self.control_dt - delta_time)
                self.counter_over_time = 0
            else:
                print("control loop over time.")
                self.counter_over_time += 1
            pass
        except Exception as e:
            print(f"[SAFETY] Exception in run(): {e}, switching to PASSIVE.")
            self.state_cmd.skill_cmd = FSMCommand.PASSIVE
            if self.joint_csv_log_enabled and self._joint_log_active:
                self._flush_joint_log("exception")
        
        pass
        
        
if __name__ == "__main__":
    config = Config()
    # Initialize DDS communication
    ChannelFactoryInitialize(0, config.net)
    
    controller = Controller(config)
    
    while True:
        try:
            controller.run()
            # Press the select key to exit
            if controller.remote_controller.is_button_pressed(KeyMap.select):
                break
        except KeyboardInterrupt:
            break

    if controller.joint_csv_log_enabled and controller._joint_log_active:
        controller._flush_joint_log("program_exit")
    
    create_damping_cmd(controller.low_cmd)
    controller.send_cmd(controller.low_cmd)
    print("Exit")
    