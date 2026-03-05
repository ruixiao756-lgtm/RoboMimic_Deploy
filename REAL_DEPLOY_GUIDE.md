# WbtDance 真机部署指南

> 适用于 Unitree G1 29DoF + whole_body_tracking 导出的 ONNX 策略

## 前置条件

### 硬件
- Unitree G1 机器人（29DoF，三自由度腰部已解锁）
- Xbox 无线手柄（**真机部署必须使用手柄**，不支持键盘）
- 以太网连接（默认网卡 `enp2s0`）
- **建议拆除手掌**（训练时未考虑手掌碰撞）
- 吊挂系统（首次测试新动作时必须）

### 软件
```bash
conda activate robomimic
# 确认依赖已安装
pip install onnx onnxruntime numpy torch
# unitree_sdk2_python 已安装
```

### 网络配置
编辑 `deploy_real/config/real.yaml`：
```yaml
net: enp2s0          # 连接机器人的网卡名称（用 ip a 查看）
num_joints: 29
lowcmd_topic: "rt/lowcmd"
lowstate_topic: "rt/lowstate"
control_dt: 0.02     # 50Hz 控制频率
error_over_time: 5
```

---

## 可用 ONNX 模型清单

按部署风险从低到高排序：

| 优先级 | 模型文件 | 动作类型 | 建议 |
|--------|---------|---------|------|
| ⭐1 | `2026-02-21_20-42-04_walk_experiment1.onnx` | **行走** | 🟢 最安全，首选部署 |
| ⭐2 | `2026-02-22_17-05-13_stand_experiment1.onnx` | **站立** | 🟢 安全 |
| 3 | `2026-02-21_23-10-04_crouch_experiment1.onnx` | **蹲下** | 🟡 重心变化大，需注意 |
| 4 | `2026-02-22_09-50-51_turn_experiment1.onnx` | **转身** | 🟡 中等风险 |
| 5 | `2026-02-25_17-30-18_sway_experiment1.onnx` | **摇摆** | 🟡 中等风险 |
| 6 | `2026-02-25_16-07-29_swing_experiment1.onnx` | **甩臂** | 🟡 上肢动作大 |
| 7 | `1policy8000OK.onnx` | **舞蹈** | 🔴 复杂动作，高风险 |
| 8 | 其他 dance_experiment*.onnx | **舞蹈** | 🔴 需先在 MuJoCo 验证 |

---

## 操作步骤

### 第一步：选择 ONNX 模型

编辑 `policy/wbt_dance/config/WbtDance.yaml`，修改模型路径：

```yaml
# 首次部署推荐使用行走模型
onnx_path: 2026-02-21_20-42-04_walk_experiment1.onnx
```

> **热重载**：WbtDance 支持每次进入策略时自动重载 YAML 配置。
> 修改 yaml 后无需重启程序，只需重新触发 R1+B 即可加载新模型。

### 第二步：先在 MuJoCo 中验证

```bash
cd /home/abc/RoboMimic_Deploy
USE_KEYBOARD=1 python deploy_mujoco/deploy_mujoco.py
```

操作流程：
1. `Enter` → 位控模式（POS_RESET）
2. `Shift + Space` (R1+A) → 行走模式（LOCO）
3. `Backspace` → 站立稳定
4. `Shift + B` (R1+B) → **触发 WbtDance**
5. 观察动作是否正常执行、是否摔倒

> ⚠️ 如果 MuJoCo 中不稳定，**不要在真机上测试**。参考 `TUNING_GUIDE.md` 调参。

### 第三步：真机部署

#### 3.1 准备
1. 开机后将机器人**吊起来**
2. 按 `L2+R2` 进入调试模式
3. 连接 Xbox 手柄

#### 3.2 启动程序
```bash
cd /home/abc/RoboMimic_Deploy
conda activate robomimic
python deploy_real/deploy_real.py
```

#### 3.3 操作流程
```
[机器人吊起状态]
  │
  ├─ 1. 按 START → 进入位控模式 (FixedPose)
  │     关节缓慢移动到默认位置
  │
  ├─ 2. 按 R1+A → 进入行走模式 (LocoMode)
  │     机器人开始维持平衡
  │
  ├─ 3. 缓慢放下机器人，确认稳定站立
  │
  ├─ 4. 按 R1+B → 触发 WbtDance（ONNX 策略）
  │     终端会显示: "Switched to wbt_dance"
  │     机器人开始执行 ONNX 模型中的动作
  │
  └─ 紧急停止:
       - 按 F1 → 阻尼保护模式 (PASSIVE)
       - 按 SELECT → 退出程序
```

---

## 手柄按键速查

| 按键组合 | 功能 | 说明 |
|---------|------|------|
| **START** | 位控复位 | 关节回默认位置 |
| **R1 + A** | 行走模式 | LocoMode |
| **R1 + X** | 查尔斯顿舞蹈 | 唯一官方验证的真机策略 |
| **R1 + B** | **WbtDance** | 你的 ONNX 策略 |
| **R1 + Y** | 武术动作 | ⚠️ 不建议真机 |
| **F1** | 🛑 阻尼保护 | **紧急停止用** |
| **SELECT** | 退出程序 | 安全退出 |
| 左摇杆 | 移动控制 | 行走模式下有效 |
| 右摇杆 | 转向控制 | 行走模式下有效 |

---

## 安全注意事项

### ⛑️ 首次部署检查清单

- [ ] MuJoCo 仿真中已验证该 ONNX 模型稳定
- [ ] `WbtDance.yaml` 中 `onnx_path` 指向正确的模型
- [ ] 机器人处于吊挂状态
- [ ] 手柄已连接且电量充足
- [ ] 有人准备在旁边扶住机器人
- [ ] 已拆除手掌（如果是舞蹈/大幅度动作）
- [ ] 地面平整、干燥、无障碍物

### 🚨 紧急处理

1. **机器人晃动/即将摔倒**：立即按 `F1`（阻尼保护）
2. **策略行为异常**：按 `SELECT` 退出程序
3. **任何不确定的情况**：先按 `F1`，再评估

### 📝 常见问题

**Q: 按 R1+B 后没有反应？**
- 确认已从 LocoMode 触发（必须先进入行走模式）
- 检查终端是否有错误信息（如 ONNX 文件不存在）

**Q: 动作太激进/机器人摔倒？**
- 在 `WbtDance.yaml` 中调低 `action_scale`（乘以 0.7-0.8）
- 调低 `joint_stiffness`（kp 乘以 0.7-0.8）
- 调高 `joint_damping`（kd 乘以 1.2-1.5）
- 详见 `TUNING_GUIDE.md`

**Q: 想切换不同 ONNX 模型？**
- 方法 1（热重载）：修改 `WbtDance.yaml` 的 `onnx_path`，按 R1+A 回到行走，再按 R1+B 重新进入 WbtDance
- 方法 2：重启程序

**Q: 真机与仿真行为差异大？**
- 正常现象（sim-to-real gap），真机通常需要更保守的参数
- 建议真机参数：kp × 0.8, kd × 1.2, action_scale × 0.9

---

## 推荐部署顺序

```
1. walk → 在吊挂状态验证，然后放下测试
2. stand → 验证站立稳定性
3. turn → 简单转身
4. crouch → 蹲下动作
5. sway/swing → 上肢动作
6. dance → 最后尝试复杂舞蹈动作
```

每个新动作都应该：
1. 先在 MuJoCo 中跑 3-5 次确认稳定
2. 真机上先在吊挂状态测试
3. 确认安全后才放下测试

---

## 技术细节

### 数据流
```
真机IMU → deploy_real.py → StateAndCmd → FSM → WbtDance.run()
  ├─ quat (w,x,y,z) → 经腰部关节补偿 → 得到 pelvis 朝向
  ├─ gyroscope (3,) → 作为 base_ang_vel 输入策略
  ├─ joint_pos (29,) → mj2lab 重排序 → IsaacLab 关节顺序
  └─ joint_vel (29,) → mj2lab 重排序 → IsaacLab 关节顺序

WbtDance 观测向量 (154维):
  [ref_joint_pos(29), ref_joint_vel(29), motion_anchor_ori_b(6),
   base_ang_vel(3), joint_pos_rel(29), joint_vel_rel(29), last_action(29)]

WbtDance 输出:
  actions → action_scale 缩放 + default_angles → 目标关节位置
  → mj2lab 逆映射回 MuJoCo 关节顺序 → PD 控制 → 关节力矩
```

### ONNX 元数据
模型自动从 ONNX 元数据读取 `default_joint_pos`、`joint_stiffness`、`joint_damping`、`action_scale`。
如果元数据缺失，回退到 `WbtDance.yaml` 的 `fallback` 配置。

设置 `use_onnx_metadata: false` 可强制使用 yaml 中的 fallback 参数（方便手动调参）。
