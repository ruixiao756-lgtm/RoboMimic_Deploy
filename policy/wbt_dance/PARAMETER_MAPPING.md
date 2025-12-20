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
