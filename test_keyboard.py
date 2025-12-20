import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.absolute()))
from common.keyboard_joystick import get_joystick
import time

joystick = get_joystick()
print("键盘测试启动...")
print("请将焦点放在弹出的 pygame 窗口上")
print("按 ESC 退出测试\n")

import pygame
running = True
while running:
    joystick.update()
    
    # 测试按钮
    buttons_status = []
    for i in range(10):
        if joystick.is_button_pressed(i):
            btn_names = ["A(Space)", "B", "X", "Y", "L1(Tab)", "R1(Shift)", "SELECT(Backspace)", "START(Enter)", "L3(C)", "R3(V)"]
            buttons_status.append(f"{btn_names[i]}")
    
    # 测试轴
    axes_status = []
    for i in range(6):
        val = joystick.get_axis_value(i)
        if abs(val) > 0.1:
            axis_names = ["LX", "LY", "RX", "RY", "LT", "RT"]
            axes_status.append(f"{axis_names[i]}:{val:.2f}")
    
    if buttons_status or axes_status:
        print(f"按钮: {', '.join(buttons_status) if buttons_status else '无'} | 轴: {', '.join(axes_status) if axes_status else '无'}")
    
    # ESC 退出
    keys = pygame.key.get_pressed()
    if keys[pygame.K_ESCAPE]:
        running = False
    
    time.sleep(0.05)

print("\n测试结束")
