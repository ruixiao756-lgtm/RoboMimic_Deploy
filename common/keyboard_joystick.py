"""Keyboard/joystick input adapter.

`deploy_mujoco/deploy_mujoco.py` expects a joystick-like object with methods:
- update()
- is_button_pressed(button_id)
- is_button_released(button_id)
- get_axis_value(axis_id)

This module provides `get_joystick()` that returns such an adapter.
"""

from __future__ import annotations

import os
import time
from typing import List, Optional


class _BaseInput:
    def get_numaxes(self) -> int:  # pragma: no cover
        raise NotImplementedError

    def get_numbuttons(self) -> int:  # pragma: no cover
        raise NotImplementedError

    def get_axis(self, i: int) -> float:  # pragma: no cover
        raise NotImplementedError

    def get_button(self, i: int) -> bool:  # pragma: no cover
        raise NotImplementedError

    def pump(self) -> None:  # pragma: no cover
        raise NotImplementedError


class _PygameKeyboardInput(_BaseInput):
    """Use keyboard to emulate a gamepad using pygame key states."""

    def __init__(self, window_title: str = "Keyboard Joystick"):
        try:
            import pygame  # type: ignore
        except Exception as e:  # pragma: no cover
            raise ModuleNotFoundError(
                "pygame is required for keyboard control. Install it in your env: `pip install pygame`"
            ) from e

        # Headless fallback (lets the program run, but keyboard control won't be useful without focus).
        if os.getenv("DISPLAY") in (None, "") and os.getenv("SDL_VIDEODRIVER") is None:
            os.environ["SDL_VIDEODRIVER"] = "dummy"

        pygame.init()
        pygame.display.set_caption(window_title)
        # 放大窗口以容纳虚拟键盘可视化
        pygame.display.set_mode((960, 360))

        self._pygame = pygame
        self._last_pump = 0.0

        self._enable_render = pygame.display.get_driver() != "dummy"
        self._surface = pygame.display.get_surface()
        self._font = pygame.font.SysFont("monospace", 16) if self._enable_render else None

        # 定义虚拟键盘布局：label, keycode, 宽度（像素）
        self._layout = [
            [
                ("Esc", pygame.K_ESCAPE, 60),
                ("1", pygame.K_1, 40), ("2", pygame.K_2, 40), ("3", pygame.K_3, 40), ("4", pygame.K_4, 40),
                ("5", pygame.K_5, 40), ("6", pygame.K_6, 40), ("7", pygame.K_7, 40), ("8", pygame.K_8, 40),
                ("9", pygame.K_9, 40), ("0", pygame.K_0, 40), ("-", pygame.K_MINUS, 40), ("=", pygame.K_EQUALS, 40),
                ("Backspace", pygame.K_BACKSPACE, 100),
            ],
            [
                ("Tab", pygame.K_TAB, 80),
                ("Q", pygame.K_q, 40), ("W", pygame.K_w, 40), ("E", pygame.K_e, 40), ("R", pygame.K_r, 40),
                ("T", pygame.K_t, 40), ("Y", pygame.K_y, 40), ("U", pygame.K_u, 40), ("I", pygame.K_i, 40),
                ("O", pygame.K_o, 40), ("P", pygame.K_p, 40), ("[", pygame.K_LEFTBRACKET, 40), ("]", pygame.K_RIGHTBRACKET, 40),
                ("\\", pygame.K_BACKSLASH, 70),
            ],
            [
                ("Caps", pygame.K_CAPSLOCK, 90),
                ("A", pygame.K_a, 40), ("S", pygame.K_s, 40), ("D", pygame.K_d, 40), ("F", pygame.K_f, 40),
                ("G", pygame.K_g, 40), ("H", pygame.K_h, 40), ("J", pygame.K_j, 40), ("K", pygame.K_k, 40),
                ("L", pygame.K_l, 40), (";", pygame.K_SEMICOLON, 40), ("'", pygame.K_QUOTE, 40),
                ("Enter", pygame.K_RETURN, 110),
            ],
            [
                ("Shift", pygame.K_LSHIFT, 110),
                ("Z", pygame.K_z, 40), ("X", pygame.K_x, 40), ("C", pygame.K_c, 40), ("V", pygame.K_v, 40),
                ("B", pygame.K_b, 40), ("N", pygame.K_n, 40), ("M", pygame.K_m, 40), (",", pygame.K_COMMA, 40),
                (".", pygame.K_PERIOD, 40), ("/", pygame.K_SLASH, 40),
                ("RShift", pygame.K_RSHIFT, 120),
            ],
            [
                ("Ctrl", pygame.K_LCTRL, 70), ("Win", pygame.K_LSUPER, 70), ("Alt", pygame.K_LALT, 70),
                ("Space", pygame.K_SPACE, 320), ("AltGr", pygame.K_RALT, 70), ("Menu", pygame.K_MENU, 70), ("RCtrl", pygame.K_RCTRL, 70),
            ],
            [
                ("Up", pygame.K_UP, 60), ("Left", pygame.K_LEFT, 60), ("Down", pygame.K_DOWN, 60), ("Right", pygame.K_RIGHT, 60),
            ],
        ]
        
        # 渲染缓存/状态，用于限频与最小化重绘开销
        self._last_render = 0.0
        # 默认 20Hz，可通过环境变量 KB_RENDER_HZ 调整（例如 10, 30）
        try:
            hz = float(os.getenv("KB_RENDER_HZ", "20"))
        except Exception:
            hz = 20.0
        if hz <= 0:
            hz = 20.0
        self._render_interval = 1.0 / hz
        self._last_keys = None

        # 预计算键位矩形和标签 surface（降低每帧开销）
        self._keycache = []  # list of (label, keycode, rect, text_surface)
        if self._enable_render and self._surface is not None and self._font is not None:
            base_x, base_y = 10, 10
            row_gap = 60
            key_gap = 8
            for row_idx, row in enumerate(self._layout):
                x = base_x
                y = base_y + row_idx * row_gap
                for label, keycode, width in row:
                    rect = (x, y, width, 44)
                    text_surf = self._font.render(label, True, (255, 255, 255))
                    self._keycache.append((label, keycode, rect, text_surf))
                    x += width + key_gap

    def _render_keyboard(self):
        if not self._enable_render or self._surface is None or self._font is None:
            return
        pygame = self._pygame
        now = time.time()
        # 限频渲染
        if now - self._last_render < self._render_interval:
            return

        keys = pygame.key.get_pressed()
        # 如果按键状态没有变化，也不必重新绘制（进一步节省）
        if self._last_keys is not None and keys == self._last_keys:
            self._last_render = now
            return

        self._surface.fill((18, 18, 18))
        for label, keycode, rect, text_surf in self._keycache:
            x, y, width, h = rect
            pressed = keys[keycode]
            bg = (70, 130, 180) if pressed else (60, 60, 60)
            border = (200, 200, 200) if pressed else (120, 120, 120)
            pygame.draw.rect(self._surface, bg, (x, y, width, h), border_radius=6)
            pygame.draw.rect(self._surface, border, (x, y, width, h), width=2, border_radius=6)
            text_rect = text_surf.get_rect(center=(x + width / 2, y + h / 2))
            self._surface.blit(text_surf, text_rect)

        pygame.display.flip()
        self._last_render = now
        self._last_keys = keys

    def pump(self) -> None:
        now = time.time()
        if now - self._last_pump > 0.005:
            self._pygame.event.pump()
            self._last_pump = now
            self._render_keyboard()

    def get_numaxes(self) -> int:
        return 6

    def get_numbuttons(self) -> int:
        return 10

    def get_axis(self, i: int) -> float:
        self.pump()
        keys = self._pygame.key.get_pressed()

        if i == 0:  # LX: A/D or left/right
            return float(keys[self._pygame.K_d] or keys[self._pygame.K_RIGHT]) - float(
                keys[self._pygame.K_a] or keys[self._pygame.K_LEFT]
            )
        if i == 1:  # LY: W/S or up/down
            return float(keys[self._pygame.K_s] or keys[self._pygame.K_DOWN]) - float(
                keys[self._pygame.K_w] or keys[self._pygame.K_UP]
            )
        if i == 2:  # RX: J/L
            return float(keys[self._pygame.K_l]) - float(keys[self._pygame.K_j])
        if i == 3:  # RY: I/K
            return float(keys[self._pygame.K_k]) - float(keys[self._pygame.K_i])
        if i == 4:  # LT: Q/E
            return float(keys[self._pygame.K_e]) - float(keys[self._pygame.K_q])
        if i == 5:  # RT: U/O
            return float(keys[self._pygame.K_o]) - float(keys[self._pygame.K_u])

        return 0.0

    def get_button(self, i: int) -> bool:
        self.pump()
        keys = self._pygame.key.get_pressed()
        mapping = {
            0: self._pygame.K_SPACE,  # A
            1: self._pygame.K_b,  # B
            2: self._pygame.K_x,  # X
            3: self._pygame.K_y,  # Y
            4: self._pygame.K_TAB,  # LB
            5: self._pygame.K_LSHIFT,  # RB
            6: self._pygame.K_BACKSPACE,  # SELECT/BACK
            # START: Enter（用于 POS_RESET -> FixedPose 姿态复位）
            7: self._pygame.K_RETURN,  # START
            8: self._pygame.K_c,  # L3
            # R3: 仿真硬重置（重新放置机器人）。键盘提供 V/F5/R 三种触发方式。
            9: (self._pygame.K_v, self._pygame.K_F5, self._pygame.K_r),  # R3
        }
        key = mapping.get(i)
        if key is None:
            return False
        # 支持单个 keycode 或 keycode 元组
        if isinstance(key, (tuple, list)):
            return any(bool(keys[k]) for k in key)
        return bool(keys[key])


class JoystickAdapter:
    """Adapter that matches the interface used by deploy_mujoco."""

    def __init__(self, backend: _BaseInput):
        self._backend = backend

        self._button_count = int(backend.get_numbuttons())
        self._axis_count = int(backend.get_numaxes())

        self._button_states: List[bool] = [False] * self._button_count
        self._button_released: List[bool] = [False] * self._button_count
        self._axis_states: List[float] = [0.0] * self._axis_count

    def update(self) -> None:
        self._backend.pump()

        prev_states = self._button_states.copy()
        self._button_released = [False] * self._button_count
        self._button_just_pressed = [False] * self._button_count
        for i in range(self._button_count):
            current = bool(self._backend.get_button(i))
            # released edge
            if self._button_states[i] and not current:
                self._button_released[i] = True
            # pressed edge
            if (not prev_states[i]) and current:
                self._button_just_pressed[i] = True
            self._button_states[i] = current

        for i in range(self._axis_count):
            self._axis_states[i] = float(self._backend.get_axis(i))

    def is_button_pressed(self, button_id: int) -> bool:
        return 0 <= int(button_id) < self._button_count and self._button_states[int(button_id)]

    def is_button_released(self, button_id: int) -> bool:
        return 0 <= int(button_id) < self._button_count and self._button_released[int(button_id)]

    def is_button_just_pressed(self, button_id: int) -> bool:
        return 0 <= int(button_id) < self._button_count and self._button_just_pressed[int(button_id)]

    def get_axis_value(self, axis_id: int) -> float:
        return 0 <= int(axis_id) < self._axis_count and self._axis_states[int(axis_id)] or 0.0


def _try_real_joystick() -> Optional[JoystickAdapter]:
    try:
        import pygame  # type: ignore
    except Exception:
        return None

    pygame.init()
    pygame.joystick.init()
    if pygame.joystick.get_count() <= 0:
        return None

    js = pygame.joystick.Joystick(0)
    js.init()

    class _PygameJoystickInput(_BaseInput):
        def __init__(self, joystick):
            self._pygame = pygame
            self._js = joystick

        def pump(self) -> None:
            self._pygame.event.pump()

        def get_numaxes(self) -> int:
            return int(self._js.get_numaxes())

        def get_numbuttons(self) -> int:
            return int(self._js.get_numbuttons())

        def get_axis(self, i: int) -> float:
            return float(self._js.get_axis(i))

        def get_button(self, i: int) -> bool:
            return bool(self._js.get_button(i))

    return JoystickAdapter(_PygameJoystickInput(js))


def get_joystick(prefer_keyboard_env: str = "USE_KEYBOARD") -> JoystickAdapter:
    """Return a joystick-like object for deploy.

    - If env `USE_KEYBOARD=1`, force keyboard.
    - Else try real joystick, and if none, fallback to keyboard.
    """

    if os.getenv(prefer_keyboard_env, "0") == "1":
        return JoystickAdapter(_PygameKeyboardInput())

    real = _try_real_joystick()
    if real is not None:
        return real

    return JoystickAdapter(_PygameKeyboardInput())
