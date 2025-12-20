# 快速调优指南：解决 MuJoCo sim 中机器人频繁摔倒问题

## 问题根因
- **tracking sigma 太小**：训练时的 reward std 参数让策略对误差容忍度低，在 MuJoCo 不同动力学下过于激进追踪导致失稳。
- **push 强度不足**：训练时随机推力范围小，策略对扰动鲁棒性不够。

---

## 方案一：无需重训的部署端快速调优（推荐先试）

### 1. 降低 kp（刚度）/ 提高 kd（阻尼）
编辑 `policy/wbt_dance/config/WbtDance.yaml`：
```yaml
fallback:
  # 原 joint_stiffness（kp）乘以 0.7~0.8，让动作更柔顺
  joint_stiffness: [28.125, 28.125, 28.125, 69.368, 69.368, 19.951,
                    28.125, 28.125, 19.951, 69.368, 69.368, 9.976,
                    9.976, 19.951, 19.951, 9.976, 9.976, 19.951,
                    19.951, 9.976, 9.976, 9.976, 9.976, 9.976,
                    9.976, 11.745, 11.745, 11.745, 11.745]
  # 原 joint_damping（kd）乘以 1.2~1.5，增加阻尼抑制震荡
  joint_damping: [3.070, 3.070, 3.070, 7.571, 7.571, 2.177,
                  3.070, 3.070, 2.177, 7.571, 7.571, 1.088,
                  1.088, 2.177, 2.177, 1.088, 1.088, 2.177,
                  2.177, 1.088, 1.088, 1.088, 1.088, 1.088,
                  1.088, 1.282, 1.282, 1.282, 1.282]
```

### 2. 降低 action_scale（减小输出幅度）
如果还不稳，可以把 `action_scale` 从 0.548/0.439 降到 0.4/0.3：
```yaml
  action_scale: [0.439, 0.439, 0.439, 0.281, 0.281, 0.351,  # 原*0.8
                 0.439, 0.439, 0.351, 0.281, 0.281, 0.351,
                 0.351, 0.351, 0.351, 0.351, 0.351, 0.351,
                 0.351, 0.351, 0.351, 0.351, 0.351, 0.351,
                 0.351, 0.060, 0.060, 0.060, 0.060]
```

### 3. 测试
```bash
cd /home/abc/RoboMimic_Deploy
USE_KEYBOARD=1 python deploy_mujoco/deploy_mujoco.py
# 按 Shift+B 或 Tab+Y 触发 WbtDance，观察是否还摔倒
```

---

## 方案二：重新训练（调高 sigma + 增强 push）

如果方案一效果不够，需要重新训练一个对 MuJoCo 更鲁棒的策略。

### 方式 1：直接修改配置文件（推荐，简单直接）

编辑 `/home/abc/whole_body_tracking/source/whole_body_tracking/whole_body_tracking/tasks/tracking/tracking_env_cfg.py`：

```python
# 第 29 行附近：把 push 强度调大 20%
VELOCITY_RANGE = {
    "x": (-0.6, 0.6),      # 原 ±0.5
    "y": (-0.6, 0.6),
    "z": (-0.24, 0.24),    # 原 ±0.2
    "roll": (-0.624, 0.624),   # 原 ±0.52
    "pitch": (-0.624, 0.624),
    "yaw": (-0.936, 0.936),    # 原 ±0.78
}

# 第 200 行附近：把 tracking sigma 调高
class RewardsCfg:
    motion_global_anchor_pos = RewTerm(
        ...
        params={"command_name": "motion", "std": 0.5},  # 原 0.3
    )
    motion_global_anchor_ori = RewTerm(
        ...
        params={"command_name": "motion", "std": 0.6},  # 原 0.4
    )
    motion_body_pos = RewTerm(
        ...
        params={"command_name": "motion", "std": 0.5},  # 原 0.3
    )
    motion_body_ori = RewTerm(
        ...
        params={"command_name": "motion", "std": 0.6},  # 原 0.4
    )
```

**已为你自动修改好！**直接用原训练命令即可（无需 Hydra 覆盖参数）。

### 方式 2：命令行 Hydra 覆盖（不改文件）
如果不想改配置文件，可以用 Hydra 语法覆盖：
```bash
python scripts/rsl_rl/train.py \
  --task Tracking-Flat-G1-Wo-State-Estimation-v0 \
  --registry_name wandb-registry-motions/dance \
  --headless \
  rewards.motion_body_pos.params.std=0.5 \
  rewards.motion_body_ori.params.std=0.6 \
  events.push_robot.params.velocity_range='{"x":[-0.6,0.6],"y":[-0.6,0.6],"z":[-0.24,0.24],"roll":[-0.624,0.624],"pitch":[-0.624,0.624],"yaw":[-0.936,0.936]}'
```

### 训练命令（已修改配置文件后）

**前提**：已自动修改 `tracking_env_cfg.py`（调好 sigma 和 push），直接用以下命令训练。

#### 方案 A：从头训练（全新实验）
```bash
cd /home/abc/whole_body_tracking

# 配置文件已改好，无需 Hydra 覆盖参数
python scripts/rsl_rl/train.py \
  --task Tracking-Flat-G1-Wo-State-Estimation-v0 \
  --registry_name wandb-registry-motions/dance \
  --num_envs 4096 \
  --headless \
  --logger wandb \
  --log_project_name my_dance_project \
  --run_name dance_mujoco_robust
```

#### 方案 B：从现有 checkpoint 继续训练（推荐，节省时间）
```bash
cd /home/abc/whole_body_tracking

python scripts/rsl_rl/train.py \
  --task Tracking-Flat-G1-Wo-State-Estimation-v0 \
  --registry_name wandb-registry-motions/dance \
  --headless \
  --logger wandb \
  --log_project_name my_dance_project \
  --run_name dance_experiment_resumed \
  --resume=true \
  --load_run 2025-12-10_20-35-11_dance_experiment \
  --checkpoint model_4500.pt
```

**注意**：
- `--load_run` 填你原实验的文件夹名（不含 `logs/rsl_rl/g1_flat/` 前缀）
- `--checkpoint` 填最新的 `.pt` 文件名（用 `ls logs/rsl_rl/g1_flat/2025-12-10_20-35-11_dance_experiment/model_*.pt` 查看）
- 续训会在原基础上微调，通常几百 iteration 就能收敛到新参数

### 参数解释
| 参数 | 原值 | 建议值 | 作用 |
|------|------|--------|------|
| `rewards.motion_body_pos.params.std` | 0.3 | **0.5** | 提高位置误差容忍度，避免策略过激追踪 |
| `rewards.motion_body_ori.params.std` | 0.4 | **0.6** | 提高姿态误差容忍度 |
| `events.push_robot.params.velocity_range.x` | [-0.5, 0.5] | **[-1.0, 1.0]** | 加强前后推力，提升抗扰动能力 |
| `events.push_robot.params.velocity_range.yaw` | [-0.78, 0.78] | **[-1.2, 1.2]** | 加强旋转扰动 |

### 训练完成后导出
```bash
python scripts/rsl_rl/play.py \
  --task Tracking-Flat-G1-Wo-State-Estimation-v0 \
  --wandb_path your-org/wbt_mujoco_robust/<run_id> \
  --disable_fabric \
  --headless
```
然后把新导出的 `exported/policy.onnx` 覆盖到 `RoboMimic_Deploy/policy/wbt_dance/model/` 即可。

---

## 推荐流程
1. **先试方案一**（5分钟）：调低 kp、调高 kd，看能否快速解决
2. 如果还不够稳，**再用方案二**（重新训练约1-2小时）

---

## 注意事项
- **不要同时调太多参数**：先试 kp*0.7 + kd*1.2，不行再降 action_scale
- **重训时记得用相同的 motion.npz**：保持动作数据一致，只改训练超参
- **Hydra 语法陷阱**：字典参数要用引号包裹，如 `'{"x":[-1.0,1.0]}'`
