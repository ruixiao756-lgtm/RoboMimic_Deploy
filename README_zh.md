<div align="center">
  <h1 align="center">RoboMimic Deploy</h1>
  <p align="center">
    <a href="README.md">🌎 English</a> | <span>🇨🇳 中文</span>
  </p>
</div>

<p align="center">
  🎮🚪 <strong>RoboMimic Deploy 是一个基于状态切换机制的机器人多策略部署框架，目前包含的策略适用于宇树G1机器人(29dof)</strong> 🚪🎮
</p>

## 写在前面

- 本部署框架仅适用于三自由度腰部已解锁的 G1（29DoF）。
- 建议拆下手掌，避免大幅动作时发生干涉。
- 当前主流程为 **BeyondMimic**；WbtDance 作为备用策略保留。
- 视频教程：[Bilibili 链接](https://www.bilibili.com/video/BV1VTKHzSE6C/?vd_source=713b35f59bdf42930757aea07a44e7cb#reply114743994027967)

---

## 安装配置

### 1) 创建虚拟环境

```bash
conda create -n robomimic python=3.8
conda activate robomimic
```

### 2) 安装依赖

```bash
conda install pytorch==2.3.1 torchvision==0.18.1 torchaudio==2.3.1 pytorch-cuda=12.1 -c pytorch -c nvidia
pip install numpy==1.20.0
pip install onnx onnxruntime
```

### 3) 安装仓库与 SDK

```bash
git clone https://github.com/ccrpRepo/RoboMimic_Deploy.git
cd RoboMimic_Deploy

git clone https://github.com/unitreerobotics/unitree_sdk2_python.git
cd unitree_sdk2_python
pip install -e .
```

### 4) 真机网络配置

编辑 `deploy_real/config/real.yaml`：

```yaml
net: enp2s0
num_joints: 29
lowcmd_topic: "rt/lowcmd"
lowstate_topic: "rt/lowstate"
control_dt: 0.02
error_over_time: 5

joint_csv_log:
  enabled: true
  output_dir: "logs/real_joint_angles"
  sample_stride: 1
  target_policies:
    - "SKILL_BEYOND_MIMIC"
```

说明：
- 开启后会在 BeyondMimic 执行期间自动记录 29 个关节角（单位：rad）。
- 默认仅记录 `SKILL_BEYOND_MIMIC`；可通过 `target_policies` 修改目标策略列表。
- 记录窗口定义为：BeyondMimic 实际开始执行时开始，退出 BeyondMimic 或热重载重启时结束并落盘。
- 每次窗口结束会自动写一份 CSV 到 `output_dir`。

### 5) 常见网络配置与排查（真机必看）

1. **确认网卡名称**（把真实网卡名填进 `real.yaml` 的 `net`）

```bash
ip a
```

常见有线网卡名：`enp2s0`、`enp3s0`、`eth0`。  
若 `real.yaml` 里的 `net` 写错，`deploy_real.py` 通常会卡在“等待低层状态”阶段。

2. **确保与机器人是同一网段**

- 电脑有线网卡需要有 IPv4 地址（不要是 `169.254.x.x` 的链路本地地址）。
- 若使用静态 IP，请按机器人网络规划设置到同一子网。
- 若使用 DHCP，确认交换机/路由器正常分配地址。

3. **基础连通性自检**

```bash
ip route
ping -c 4 <机器人IP>
```

- `ping` 丢包高或不可达时，不建议直接上控制程序。
- 先更换网线、网口，再检查 IP 配置。

4. **避免网络冲突**

- 运行真机控制时，建议临时关闭 VPN、代理、虚拟网卡优先路由。
- 尽量只保留一条到机器人网络的默认路径（避免流量走错网卡）。

5. **启动前快速检查清单**

- `real.yaml` 的 `net` 与 `ip a` 输出一致
- 有线网口 `state UP`
- 能 `ping` 通机器人
- 手柄已连接、机器人已进入调试模式（`L2+R2`）

6. **典型故障现象与处理**

- 现象：程序启动后长期无动作、无状态更新  
  处理：优先检查 `net` 是否写错、网线是否断开、是否同网段。
- 现象：偶发控制卡顿或超时报警（`control loop over time`）  
  处理：关闭后台占用、确认网络稳定、降低同时运行的可视化/录屏负载。
- 现象：能连上但动作异常延迟  
  处理：检查交换机质量和链路速率，优先直连或使用稳定千兆交换机。

### 6) 不连真机的 CSV 流程验证

可在 `robomimic` 环境下直接验证“BeyondMimic 开始记录，退出 BeyondMimic 自动落盘”流程：

```bash
cd /home/abc/RoboMimic_Deploy
conda run -n robomimic python tools/verify_joint_csv_flow.py
```

若输出 `PASS: offline joint CSV flow verified`，说明 CSV 记录逻辑链路已打通。

---

## Policy 说明

| 模式名称 | 描述 |
|---|---|
| PassiveMode | 阻尼保护模式 |
| FixedPose | 位控恢复默认关节值 |
| LocoMode | 稳定行走模式 |
| Dance | 查尔斯顿舞蹈 |
| KungFu | 武术动作 |
| BeyondMimic | 当前主用 ONNX 策略（`policy/beyond_mimic`） |
| WbtDance | 备用 ONNX 策略（`policy/wbt_dance`） |
| SkillCast | Mimic 前过渡模式 |
| SkillCooldown | Mimic 后过渡模式 |

---

## BeyondMimic 部署（主流程）

### 第一步：配置 ONNX

编辑 `policy/beyond_mimic/config/BeyondMimic.yaml`：

```yaml
onnx_path: "2026-03-08_14-35-39_walk_to_stand_32768_a100.onnx"
motion_length: "auto"
terminal_behavior: "hold_last_frame"   # 可选: "switch_to_loco"
```

参数说明：
- `motion_length: "auto"`：自动按 ONNX 参考轨迹长度执行。
- `terminal_behavior: "hold_last_frame"`：结束后保持最后一帧关节目标。
- `terminal_behavior: "switch_to_loco"`：结束后自动切回 LocoMode。

### 第二步：先做 MuJoCo 验证

```bash
cd /home/abc/RoboMimic_Deploy
USE_KEYBOARD=1 python deploy_mujoco/deploy_mujoco.py
```

流程建议：
1. `Enter` 进入位控（POS_RESET）
2. `Shift+Space`（R1+A）进入行走（LOCO）
3. `Backspace` 观察站立稳定
4. `Tab+T`（L1+HOME）触发 BeyondMimic
5. 观察是否稳定、结尾是否符合 `terminal_behavior`

> 若仿真不稳定，不要直接上真机。

### 第三步：真机部署

```bash
cd /home/abc/RoboMimic_Deploy
conda activate robomimic
python deploy_real/deploy_real.py
```

流程建议：L2+B,
1. 机器人吊挂，`L2+R2` 进调试模式
2. `START` 进入位控（FixedPose）
3. `R1+A` 进入行走（LocoMode）
4. 缓慢放下确认稳定
5. `R1+B` 触发 BeyondMimic

---

## 按键说明

### 真机手柄按键

| 按键 | 功能 |
|---|---|
| START | 位控复位 |
| R1 + A | 行走模式（LocoMode） |
| R1 + X | Dance |
| R1 + Y | KungFu |
| R1 + B | BeyondMimic（当前主流程；在该模式下再次按可热重载） |
| L1 + Y | WbtDance（备用） |
| F1 | 阻尼保护（PASSIVE） |
| SELECT | 退出程序 |

### MuJoCo 键盘映射（无手柄）

启动：

```bash
USE_KEYBOARD=1 python deploy_mujoco/deploy_mujoco.py
```

按钮映射：
- `Enter` = Start
- `Backspace` = Select
- `Left Shift` = R1
- `Tab` = L1
- `Space` = A
- `X` = X
- `Y` = Y
- `B` = B

摇杆映射：
- 左摇杆：`WASD` 或方向键
- 右摇杆：`IJKL`

---

## 推荐模型顺序（BeyondMimic）

按风险从低到高：
1. `2026-02-21_20-42-04_walk_experiment1.onnx`
2. `2026-02-22_17-05-13_stand_experiment1.onnx`
3. `2026-02-21_23-10-04_crouch_experiment1.onnx`
4. `2026-02-22_09-50-51_turn_experiment1.onnx`
5. `2026-02-25_17-30-18_sway_experiment1.onnx`
6. `2026-02-25_16-07-29_swing_experiment1.onnx`
7. `2026-03-08_14-35-39_walk_to_stand_32768_a100.onnx`
8. 其他 `dance_experiment*.onnx`

---

## 常见问题

**Q: R1+B 触发后没反应？**
- 先确认当前已在 LocoMode。
- 检查 `BeyondMimic.yaml` 里的 `onnx_path` 是否存在。

**Q: 动作结束后没切回行走？**
- 设为 `terminal_behavior: "switch_to_loco"`。
- 若是 `hold_last_frame`，不会自动切模式。

**Q: 结尾没站住怎么办？**
- 优先尝试 `switch_to_loco`。
- 或保留 `hold_last_frame`，先确认该 ONNX 最后一帧本身稳定。

**Q: 动作太激进？**
- 降低 `action_scale_lab`（0.7~0.9 倍）
- 降低 `kp_lab`（0.7~0.9 倍）
- 提高 `kd_lab`（1.1~1.4 倍）

---

## 安全与注意事项

- 首次测试新动作必须吊挂。
- 地面湿滑/复杂地形会显著降低 Mimic 成功率。
- 出现异常时优先按 `F1` 进入阻尼保护。
- 先仿真反复验证，再上真机。

兼容性说明：当前框架暂不支持 Orin NX 平台直接部署。若需机载部署，建议使用 `unitree_sdk2` + ROS 双节点（C++通信 + Python推理）。



