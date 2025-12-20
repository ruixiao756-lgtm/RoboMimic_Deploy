import time
from common.keyboard_joystick import get_joystick

# Short perf test: call update() in a tight loop for a few seconds and measure timings
if __name__ == '__main__':
    js = get_joystick()
    print('Started joystick perf test. Click the pygame window if visible to enable events.')
    durations = []
    renders = 0
    start = time.time()
    end_time = start + 5.0
    while time.time() < end_time:
        t0 = time.time()
        js.update()
        t1 = time.time()
        durations.append(t1 - t0)
        time.sleep(0.005)
    total = sum(durations)
    cnt = len(durations)
    print(f'Calls: {cnt}, total_time={total:.4f}s, avg_call={total/cnt*1000:.3f} ms')
    print(f'min={min(durations)*1000:.3f} ms, max={max(durations)*1000:.3f} ms')
    print('Test complete.')
