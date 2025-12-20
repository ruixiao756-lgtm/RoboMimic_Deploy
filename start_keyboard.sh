#!/bin/bash
# 键盘控制版 MuJoCo 部署启动脚本

cd /home/abc/RoboMimic_Deploy

echo "========================================="
echo "  RoboMimic 键盘控制版启动脚本"
echo "========================================="
echo ""
echo "注意事项："
echo "1. 会同时打开两个窗口："
echo "   - MuJoCo 仿真窗口 (大窗口)"
echo "   - Pygame 键盘输入窗口 (小窗口 240x120)"
echo ""
echo "2. 按键前必须点击 Pygame 小窗口使其获得焦点！"
echo ""
echo "3. 常用操作："
echo "   - Enter (回车) = START 按钮 → 进入位控模式"
echo "   - Left Shift + Space = R1+A → 进入行走模式"
echo "   - Backspace = SELECT → 机器人站立/阻尼模式"
echo "   - WASD/方向键 = 控制移动"
echo ""
echo "4. 终端会显示模式切换信息"
echo ""
echo "按任意键开始启动..."
read -n 1 -s

echo ""
echo "启动中..."
conda activate robomimic
USE_KEYBOARD=1 python deploy_mujoco/deploy_mujoco.py
