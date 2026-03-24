"""
RaspiCameraProvider - Hardware test script.

Tested APIs:
  start, stop, is_running, data

Prerequisites:
  Raspberry Pi Camera Module connected and Picamera2 installed

Usage:
  python3 src/providers/test_raspi_camera_provider.py

Controls (visualization window):
  q / ESC  - quit
"""

import sys
import time
import cv2
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.providers.raspi_camera_provider import CameraFrame, RaspiCameraProvider

def _draw_overlay(cv2, frame: CameraFrame):
    bgr = frame.bgr
    h, w = bgr.shape[:2]

    def put(text: str, y: int, color=(0, 255, 0)) -> None:
        cv2.putText(bgr, text, (8, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(bgr, text, (8, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 1, cv2.LINE_AA)

    put(f"FPS: {float(frame.camera_fps):.2f}", 24)
    put(f"Frame: {int(frame.frame_cnt)}", 48)
    put(f"Size: {w}x{h}", 72)
    put(f"Timestamp: {float(frame.t_monotonic):.3f}", 96, color=(255, 200, 0))
    return bgr


def main() -> int:
    # -------------------------------------------------------------------------
    # Phase 0: Setup
    # -------------------------------------------------------------------------
    print(f"\n{'=' * 60}\n  Phase 0: Setup\n{'=' * 60}")
    provider = RaspiCameraProvider()
    print("  Provider created")
    print("  OK")

    # -------------------------------------------------------------------------
    # Phase 1: Start
    # -------------------------------------------------------------------------
    print(f"\n{'=' * 60}\n  Phase 1: Start\n{'=' * 60}")
    try:
        provider.start()
    except RuntimeError as exc:
        print(f"  FAIL: {exc}")
        return 1
    print(f"  provider.is_running: {provider.is_running}")
    print("  start()\n  OK")

    # -------------------------------------------------------------------------
    # Phase 2: Frame verification
    # -------------------------------------------------------------------------
    print(f"\n{'=' * 60}\n  Phase 2: Frame verification\n{'=' * 60}")
    first_frame = provider.data
    if first_frame is None:
        print("  FAIL: provider.data returned None after successful start()")
        provider.stop()
        return 1

    bgr = first_frame.bgr
    print(f"  bgr shape={tuple(bgr.shape)}  dtype={bgr.dtype}")
    print(f"  camera_fps={float(first_frame.camera_fps):.2f}")
    print(f"  frame_cnt={int(first_frame.frame_cnt)}")
    print(f"  width={int(first_frame.width)}  height={int(first_frame.height)}")
    print(f"  timestamp={float(first_frame.t_monotonic):.6f}")
    print("  OK")

    # -------------------------------------------------------------------------
    # Phase 3: Live visualization
    # -------------------------------------------------------------------------
    print(f"\n{'=' * 60}\n  Phase 3: Live visualization\n{'=' * 60}")
    print("  Press 'q' or ESC in the window to quit.")
    
    window_name = "RaspiCamera HW Test (q/ESC to quit)"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    while True:
        frame = provider.data
        if frame is None:
            time.sleep(0.01)
            continue

        display = _draw_overlay(cv2, frame)
        cv2.imshow(window_name, display)

        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), 27):
            break

    cv2.destroyAllWindows()
    print("  Visualization closed.")

    # -------------------------------------------------------------------------
    # Phase 4: Teardown
    # -------------------------------------------------------------------------
    print(f"\n{'=' * 60}\n  Phase 4: Teardown\n{'=' * 60}")
    provider.stop()
    print(f"  provider.is_running: {provider.is_running}")
    print("  stop()\n  OK")

    print("\n  All phases complete. Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
