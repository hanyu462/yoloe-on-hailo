from dataclasses import dataclass
import logging
import threading
import time
from picamera2 import Picamera2

from typing import Any, Optional


@dataclass(slots=True)
class CameraFrame:
    t_monotonic: float
    bgr: Any
    camera_fps: float
    frame_cnt: int
    width: int
    height: int


class RaspiCameraProvider:
    """
    Raspberry Pi Camera Module provider.

    - Picamera2를 사용해 background thread에서 최신 프레임을 계속 읽는다.
    - `get_data()`는 가장 최근 프레임 정보를 `CameraFrame`으로 반환한다.
    - Picamera2 `RGB888` main stream은 OpenCV용 `[B, G, R]` 배열로 capture 된다.
    """

    def __init__(
        self,
        camera_index: int = 0,
        width: int = 640,
        height: int = 480,
        fps: int = 30,
    ) -> None:
        self.camera_index = int(camera_index)
        self.width = int(width)
        self.height = int(height)
        self.fps = int(fps)

        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        self._camera: Any = None
        self._data: Optional[CameraFrame] = None
        self._frame_cnt = 0
        self._last_frame_time: Optional[float] = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            logging.warning("RaspiCameraProvider already running")
            return

        self._start_picamera()
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            with self._lock:
                if self._data is not None:
                    break
            time.sleep(0.01)
        else:
            self.stop()
            raise RuntimeError("RaspiCameraProvider: timed out waiting for first frame")

        logging.info("RaspiCameraProvider started")

    def stop(self) -> None:
        self._stop_event.set()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None

        camera = self._camera
        self._camera = None
        self._frame_cnt = 0
        self._last_frame_time = None

        if camera is not None:
            try:
                camera.stop()
            except Exception as exc:
                logging.warning("RaspiCameraProvider stop error: %s", exc)

            try:
                camera.close()
            except Exception as exc:
                logging.warning("RaspiCameraProvider close error: %s", exc)

        with self._lock:
            self._data = None
        logging.info("RaspiCameraProvider stopped")

    def get_data(self) -> Optional[CameraFrame]:
        with self._lock:
            return self._data

    def _start_picamera(self) -> None:
        if self._camera is not None:
            return

        self._camera = Picamera2(camera_num=self.camera_index)

        config = self._camera.create_video_configuration(
            main={"size": (self.width, self.height), "format": "RGB888"},
            controls={"FrameRate": self.fps},
            buffer_count=4,
            queue=False,
        )
        self._camera.configure(config)
        self._camera.start()

        for _ in range(5):
            self._camera.capture_array("main")

        self._frame_cnt = 0
        self._last_frame_time = None

    def _read_frame(self) -> CameraFrame:
        if self._camera is None:
            raise RuntimeError("Camera not started. Call start() first")

        bgr = self._camera.capture_array("main")
        timestamp = time.monotonic()

        if self._last_frame_time is None:
            camera_fps = float(self.fps)
        else:
            dt = timestamp - self._last_frame_time
            camera_fps = 0.0 if dt <= 0 else 1.0 / dt

        self._last_frame_time = timestamp
        self._frame_cnt += 1

        return CameraFrame(
            t_monotonic=timestamp,
            bgr=bgr,
            camera_fps=camera_fps,
            frame_cnt=self._frame_cnt,
            width=int(bgr.shape[1]),
            height=int(bgr.shape[0]),
        )

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                frame = self._read_frame()
                with self._lock:
                    self._data = frame
            except Exception as exc:
                logging.error("RaspiCameraProvider run loop error: %s", exc)
                with self._lock:
                    self._data = None
                time.sleep(0.1)
