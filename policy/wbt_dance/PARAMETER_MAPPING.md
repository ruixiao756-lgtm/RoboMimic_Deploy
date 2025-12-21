# WbtDance 参数映射指南

## 概述
`env.yaml` 使用关节名称（regex 匹配）定义参数，`WbtDance.yaml` 使用数组索引（按 IsaacLab 关节顺序）。

## 关节顺序映射

### mj2lab 数组的含义
`mj2lab = [0, 6, 12, 1, 7, 13, 2, 8, 14, 3, 9, 15, 22, 4, 10, 16, 23, 5, 11, 17, 24, 18, 25, 19, 26, 20, 27, 21, 28]`

- **数组索引** = IsaacLab 关节顺序（0-28，共29个关节）
- **数组值** = MuJoCo 关节顺序

### IsaacLab 关节顺序（WbtDance.yaml 数组索引）

| 索引 | 关节名称 | env.yaml 分组 | mj2lab值 |
|------|---------|---------------|----------|
| 0 | left_hip_yaw_joint | legs | 0 |
| 1 | left_hip_roll_joint | legs | 6 |
| 2 | left_hip_pitch_joint | legs | 12 |
| 3 | left_knee_joint | legs | 1 |
| 4 | left_ankle_pitch_joint | feet | 7 |
| 5 | left_ankle_roll_joint | feet | 13 |
| 6 | right_hip_yaw_joint | legs | 2 |
| 7 | right_hip_roll_joint | legs | 8 |
| 8 | right_hip_pitch_joint | legs | 14 |
| 9 | right_knee_joint | legs | 3 |
| 10 | right_ankle_pitch_joint | feet | 9 |
| 11 | right_ankle_roll_joint | feet | 15 |
| 12 | waist_yaw_joint | waist_yaw | 22 |
| 13 | waist_roll_joint | waist | 4 |
| 14 | waist_pitch_joint | waist | 10 |
| 15 | left_shoulder_pitch_joint | arms | 16 |
| 16 | left_shoulder_roll_joint | arms | 23 |
| 17 | left_shoulder_yaw_joint | arms | 5 |
| 18 | left_elbow_joint | arms | 11 |
| 19 | left_wrist_roll_joint | arms | 17 |
| 20 | left_wrist_pitch_joint | arms | 24 |
| 21 | left_wrist_yaw_joint | arms | 18 |
| 22 | right_shoulder_pitch_joint | arms | 25 |
| 23 | right_shoulder_roll_joint | arms | 19 |
| 24 | right_shoulder_yaw_joint | arms | 26 |
| 25 | right_elbow_joint | arms | 20 |
| 26 | right_wrist_roll_joint | arms | 27 |
| 27 | right_wrist_pitch_joint | arms | 21 |
| 28 | right_wrist_yaw_joint | arms | 28 |

## 参数映射：env.yaml → WbtDance.yaml

### 1. joint_stiffness (kp)

#### env.yaml 定义：
```yaml
scene.robot.actuators:
  legs:  # 索引 0,1,2,3,6,7,8,9
    stiffness:
      .*_hip_pitch_joint: 40.179    # 索引 2, 8
      .*_hip_roll_joint: 99.098     # 索引 1, 7
      .*_hip_yaw_joint: 40.179      # 索引 0, 6
      .*_knee_joint: 99.098         # 索引 3, 9
  
  feet:  # 索引 4,5,10,11
    stiffness: 28.501               # 索引 4,5,10,11
  
  waist:  # 索引 13,14
    stiffness: 28.501               # 索引 13,14
  
  waist_yaw:  # 索引 12
    stiffness: 40.179               # 索引 12
  
  arms:  # 索引 15-28
    stiffness:
      .*_shoulder_pitch_joint: 14.251   # 索引 15, 22
      .*_shoulder_roll_joint: 14.251    # 索引 16, 23
      .*_shoulder_yaw_joint: 14.251     # 索引 17, 24
      .*_elbow_joint: 14.251            # 索引 18, 25
      .*_wrist_roll_joint: 14.251       # 索引 19, 26
      .*_wrist_pitch_joint: 16.778      # 索引 20, 27
      .*_wrist_yaw_joint: 16.778        # 索引 21, 28
```

#### WbtDance.yaml 数组（按 IsaacLab 顺序 0-28）：
```yaml
joint_stiffness:
- 40.179   # 0: left_hip_yaw
- 40.179   # 1: left_hip_roll → 应为 99.098
- 40.179   # 2: left_hip_pitch
- 99.098   # 3: left_knee
- 99.098   # 4: left_ankle_pitch → 应为 28.501
- 28.501   # 5: left_ankle_roll
- 40.179   # 6: right_hip_yaw
- 40.179   # 7: right_hip_roll → 应为 99.098
- 28.501   # 8: right_hip_pitch → 应为 40.179
- 99.098   # 9: right_knee
- 99.098   # 10: right_ankle_pitch → 应为 28.501
- 14.251   # 11: right_ankle_roll → 应为 28.501
- 14.251   # 12: waist_yaw → 应为 40.179
- 28.501   # 13: waist_roll
- 28.501   # 14: waist_pitch
- 14.251   # 15: left_shoulder_pitch
- 14.251   # 16: left_shoulder_roll
- 28.501   # 17: left_shoulder_yaw → 应为 14.251
- 28.501   # 18: left_elbow → 应为 14.251
- 14.251   # 19: left_wrist_roll
- 14.251   # 20: left_wrist_pitch → 应为 16.778
- 14.251   # 21: left_wrist_yaw → 应为 16.778
- 14.251   # 22: right_shoulder_pitch
- 14.251   # 23: right_shoulder_roll
- 14.251   # 24: right_shoulder_yaw
- 14.251   # 25: right_elbow
- 16.778   # 26: right_wrist_roll → 应为 14.251
- 16.778   # 27: right_wrist_pitch
- 16.778   # 28: right_wrist_yaw
```

**发现：当前 WbtDance.yaml 的参数有错误！** ONNX metadata 提取的参数与 env.yaml 不完全匹配。

### 2. joint_damping (kd) - 同理

### 3. action_scale

#### env.yaml 定义（actions.joint_pos.scale）：
```yaml
.*_hip_yaw_joint: 0.5475        # 索引 0, 6
.*_hip_roll_joint: 0.3507       # 索引 1, 7
.*_hip_pitch_joint: 0.5475      # 索引 2, 8
.*_knee_joint: 0.3507           # 索引 3, 9
.*_ankle_pitch_joint: 0.4386    # 索引 4, 10
.*_ankle_roll_joint: 0.4386     # 索引 5, 11
waist_roll_joint: 0.4386        # 索引 13
waist_pitch_joint: 0.4386       # 索引 14
waist_yaw_joint: 0.5475         # 索引 12
.*_shoulder_pitch_joint: 0.4386 # 索引 15, 22
.*_shoulder_roll_joint: 0.4386  # 索引 16, 23
.*_shoulder_yaw_joint: 0.4386   # 索引 17, 24
.*_elbow_joint: 0.4386          # 索引 18, 25
.*_wrist_roll_joint: 0.4386     # 索引 19, 26
.*_wrist_pitch_joint: 0.0745    # 索引 20, 27
.*_wrist_yaw_joint: 0.0745      # 索引 21, 28
```

## 修改参数的正确方法

### 方法1：直接编辑 WbtDance.yaml（推荐）
找到对应的数组索引，直接修改数值。例如要调整左膝盖刚度：
```yaml
joint_stiffness:
  # ... 前面的值
  - 99.098   # 索引 3: left_knee_joint，改成你想要的值
```

### 方法2：从 env.yaml 同步（需要写脚本）
如果你修改了 env.yaml，需要按上述映射关系手动同步到 WbtDance.yaml。

### 方法3：重新导出 ONNX
在 IsaacLab 中修改环境配置，重新训练或导出 ONNX（ONNX 会自动嵌入正确的参数）。

## 注意事项

1. **mj2lab 映射**：WbtDance.py 使用 `mj2lab` 数组在运行时转换 MuJoCo↔IsaacLab 关节顺序
2. **ONNX metadata 优先**：如果 `use_onnx_metadata: true`，会优先使用 ONNX 内嵌参数，fallback 仅在读取失败时使用
3. **调参建议**：
   - 降低刚度(stiffness)可让动作更柔顺
   - 提高阻尼(damping)可减少震荡
   - 降低 action_scale 可减小动作幅度

## 快速查找表

要修改某个关节的参数，在 WbtDance.yaml 的数组中找对应索引：

| 想修改的关节 | WbtDance.yaml 索引 |
|-------------|-------------------|
| 左髋偏航 left_hip_yaw | 0 |
| 左髋侧摆 left_hip_roll | 1 |
| 左髋俯仰 left_hip_pitch | 2 |
| 左膝 left_knee | 3 |
| 左踝俯仰 left_ankle_pitch | 4 |
| 左踝侧摆 left_ankle_roll | 5 |
| 右髋偏航 right_hip_yaw | 6 |
| 右髋侧摆 right_hip_roll | 7 |
| 右髋俯仰 right_hip_pitch | 8 |
| 右膝 right_knee | 9 |
| 右踝俯仰 right_ankle_pitch | 10 |
| 右踝侧摆 right_ankle_roll | 11 |
| 腰偏航 waist_yaw | 12 |
| 腰侧摆 waist_roll | 13 |
| 腰俯仰 waist_pitch | 14 |
| 左肩俯仰 left_shoulder_pitch | 15 |
| 左肩侧摆 left_shoulder_roll | 16 |
| 左肩偏航 left_shoulder_yaw | 17 |
| 左肘 left_elbow | 18 |
| 左腕侧摆 left_wrist_roll | 19 |
| 左腕俯仰 left_wrist_pitch | 20 |
| 左腕偏航 left_wrist_yaw | 21 |
| 右肩俯仰 right_shoulder_pitch | 22 |
| 右肩侧摆 right_shoulder_roll | 23 |
| 右肩偏航 right_shoulder_yaw | 24 |
| 右肘 right_elbow | 25 |
| 右腕侧摆 right_wrist_roll | 26 |
| 右腕俯仰 right_wrist_pitch | 27 |
| 右腕偏航 right_wrist_yaw | 28 |
# ==========================================
# WbtDance 策略部署配置 - 参数调优指南
# ==========================================
# 原参数来源：从 ONNX 模型元数据自动提取
# 当前策略特点：相对保守，稳定性强，但动作可能略显滞后
#
# ==================== 参数调优指南 ====================
#
# 1. joint_stiffness (kp) - 关节刚度
#    ┌─ 降低数值的影响：
#    │  • 关节更柔顺，动作更流畅，抖动减少
#    │  • 对外界扰动的抗性降低，易摔倒（MuJoCo模拟推力时）
#    │  • 跟踪精度下降，可能无法精准执行快速动作
#    │
#    └─ 提高数值的影响：
#       • 关节更硬，动作更刚性，抖动增加
#       • 对外界扰动的抗性提高，稳定性更好
#       • 消耗更多能量，可能触发关节限制告警
#
#    当前值评估：保守 → 激进调整建议
#    • 保守(稳定优先)：乘以 0.7-0.8  (如 99.098 → 70-80)
#    • 平衡：保持现状 (99.098)
#    • 激进(精度优先)：乘以 1.2-1.5  (如 99.098 → 120-150)
#    • 极端激进：乘以 2.0+  (如 99.098 → 200+，风险高)
#
# 2. joint_damping (kd) - 关节阻尼
#    ┌─ 降低数值的影响：
#    │  • 阻尼减少，动作响应更快，但易产生振荡
#    │  • 高速运动时不稳定，可能产生左右摇晃
#    │
#    └─ 提高数值的影响：
#       • 阻尼增加，振荡衰减快，运动更稳定
#       • 但会延缓运动响应，动作变"肉"
#       • 过高会导致关节跟不上目标位置
#
#    当前值评估：中等 → 激进调整建议
#    • 保守(防振荡)：乘以 1.2-1.5  (如 6.309 → 7.5-9.5)
#    • 平衡：保持现状 (6.309)
#    • 激进(快速响应)：乘以 0.7-0.8  (如 6.309 → 4.4-5.0)
#    • 极端激进：乘以 0.5  (如 6.309 → 3.15，需谨慎测试)
#
# 3. action_scale - 动作幅度缩放
#    ┌─ 降低数值的影响：
#    │  • 关节运动幅度减小，动作更"缩手缩脚"
#    │  • 激烈动作（跳跃、旋转）性能下降
#    │  • 摔倒风险降低（运动范围受限）
#    │
#    └─ 提高数值的影响：
#       • 关节运动幅度增大，动作更夸张
#       • 激烈动作表现更好，但易失控
#       • 可能触发关节物理限制（工作空间外）
#
#    当前值评估：中等保守 → 激进调整建议
#    # 双腿关节 (hip/knee): 0.548/0.351
#    • 保守：乘以 0.8  (0.548 → 0.44, 0.351 → 0.28)
#    • 平衡：保持现状  (0.548, 0.351)
#    • 激进：乘以 1.2-1.3  (0.548 → 0.65-0.71, 0.351 → 0.42-0.46)
#    • 极端激进：乘以 1.5+  (0.548 → 0.82+)
#
#    # 手臂/手腕关节: 0.439/0.075
#    • 保守：乘以 0.7  (0.439 → 0.31, 0.075 → 0.05)
#    • 平衡：保持现状  (0.439, 0.075)
#    • 激进：乘以 1.3-1.5  (0.439 → 0.57-0.66, 0.075 → 0.10-0.11)
#
# ==================== 综合调参策略 ====================
#
# 场景 1: 动作太"肉"，跟踪滞后
#   → 降低 kd (阻尼)，提高 kp (刚度)，提高 action_scale
#   推荐: kd × 0.8, kp × 1.2, action_scale × 1.2
#
# 场景 2: 动作抖动厉害，易摔倒
#   → 提高 kd (阻尼)，降低 kp (刚度)，降低 action_scale
#   推荐: kd × 1.3, kp × 0.8, action_scale × 0.9
#
# 场景 3: 原数据保守，要更激进表现
#   → 小幅提高 kp，小幅降低 kd，适度提高 action_scale
#   推荐: kp × 1.1-1.2, kd × 0.9-1.0, action_scale × 1.1-1.2
#
# 场景 4: 只想加强某些部位的表现
#   → 精确修改对应关节的参数（见下方注释的索引对应表）
#
# ==================== 测试建议 ====================
# 1. 每次修改参数幅度不超过 ±20%，避免剧烈波动
# 2. 修改后先在 MuJoCo 模拟跑 1-2 个 episode 观察表现
# 3. 记录修改前后的对比（参数值 + 动作质量评分）
# 4. 如果效果不理想，回滚到上一个配置，微调改动幅度
# 5. 最终满意的参数可保存到 git，便于对比和回溯
#
# ==========================================
髋俯仰 (hip_pitch)

轴：pitch（绕 y 轴）
动作：大腿前后摆（抬腿/后伸），控制步态步幅和前后 CoM 位移。
对平衡：非常重要 —— 前倾/后仰直接改变质心前后位置。
髋滚转/侧摆 (hip_roll)

轴：roll（绕 x 轴）
动作：大腿向侧外展/内收（把腿往外/往内），影响横向支撑和侧向稳定。
对平衡：影响侧向稳定性，配合踝/膝保持不倒。
髋偏航 (hip_yaw)

轴：yaw（绕 z 轴）
动作：大腿相对于身体旋转（扭转），影响脚尖朝向与步态方向。
对平衡：对横向/前后影响较小，但影响运动方向控制与步态匹配。
膝 (knee)（通常是 knee_pitch）

轴：pitch（绕 y 轴）
动作：屈伸（抬腿、蹲起），影响支撑高度与承重。
对平衡：非常关键，决定地面反作用力分配与缓冲。
踝（ankle_pitch / ankle_roll）

ankle_pitch：绕 y 轴（前后）—— 控制脚尖抬/放，调节前后平衡。
ankle_roll：绕 x 轴（侧向）—— 控制内外侧倾斜，调节侧向平衡。
对平衡：和膝/髋一起决定支撑稳定性，常用于微调 CoM。
腰 / 躯干（waist_yaw, waist_roll, waist_pitch）

yaw/roll/pitch 如上，腰的 pitch（前后）是导致“后仰”问题的关键关节之一。
对平衡：腰部动作直接移动上半身质心，高幅度前/后动作会让机器人需要用腿部大幅补偿。
肩膀（shoulder_pitch / shoulder_roll / shoulder_yaw）

shoulder_pitch：绕 y 轴 —— 手臂向前/向后摆（影响前后质心）
shoulder_roll：绕 x 轴 —— 手臂抬到侧面/放下（影响侧向质心）
shoulder_yaw：绕 z 轴 —— 上臂绕竖轴旋转（主要是方向/姿态，不大改变 CoM）
对平衡：手臂对 CoM 有影响（尤其是大幅度摆动），但量级通常小于腿/躯干；可用于细调姿态或抵消动作。
肘（elbow，通常是 elbow_pitch）

轴：pitch（屈伸）—— 改变前臂角度，对整体质心影响小，但影响手臂配置（惯量分布）。
腕（wrist_roll/pitch/yaw）

wrist_roll：旋转前臂（拧腕）—— 对 CoM 几乎无影响
wrist_pitch/yaw：手腕上下/左右动—— 同样对 CoM 影响很小
