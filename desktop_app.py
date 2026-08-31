from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import os
import sys
import threading
import traceback
from pathlib import Path

from backend.app_paths import LOG_DIR, WEBVIEW_DATA_DIR
from backend.server import create_server


APP_TITLE = "星图寻迹 · 星空照片识别与标注"
MUTEX_NAME = "Local\\StarfieldAtlasDesktop-3D14B123-822E-4A6A-9D5C-5CFEE8B15685"
ERROR_ALREADY_EXISTS = 183


def _message_box(message: str, title: str = "星图寻迹") -> None:
    try:
        ctypes.windll.user32.MessageBoxW(None, message, title, 0x10)
    except Exception:
        pass


def _acquire_single_instance() -> int | None:
    if os.name != "nt":
        return 1
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL
    handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if not handle:
        return None
    if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(handle)
        return None
    return int(handle)


def _write_crash_log(exc: BaseException) -> Path | None:
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        path = LOG_DIR / "desktop-startup-error.log"
        path.write_text(
            "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
            encoding="utf-8",
        )
        return path
    except OSError:
        return None


def _run_server_only(host: str, port: int) -> None:
    server = create_server(host, port)
    try:
        server.serve_forever(poll_interval=0.2)
    finally:
        server.server_close()


def _run_desktop() -> None:
    instance_handle = _acquire_single_instance()
    if instance_handle is None:
        _message_box("星图寻迹已经在运行。请切换到现有窗口。", "星图寻迹")
        return

    server = create_server("127.0.0.1", 0)
    port = int(server.server_address[1])
    server_thread = threading.Thread(
        target=server.serve_forever,
        kwargs={"poll_interval": 0.2},
        name="starfield-atlas-http",
        daemon=True,
    )
    server_thread.start()

    try:
        import webview

        WEBVIEW_DATA_DIR.mkdir(parents=True, exist_ok=True)
        if hasattr(webview, "settings"):
            webview.settings["ALLOW_DOWNLOADS"] = True
        webview.create_window(
            APP_TITLE,
            f"http://127.0.0.1:{port}",
            width=1440,
            height=900,
            min_size=(960, 640),
            background_color="#080d10",
            text_select=False,
        )
        webview.start(
            gui="edgechromium",
            debug=False,
            private_mode=False,
            storage_path=str(WEBVIEW_DATA_DIR),
        )
    except BaseException as exc:
        log_path = _write_crash_log(exc)
        location = f"\n\n错误记录：{log_path}" if log_path else ""
        _message_box(
            "无法启动桌面窗口。请确认 Microsoft Edge WebView2 Runtime 已安装。"
            f"{location}",
            "星图寻迹启动失败",
        )
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=2)
        if os.name == "nt" and instance_handle:
            ctypes.windll.kernel32.CloseHandle(wintypes.HANDLE(instance_handle))


def main() -> None:
    parser = argparse.ArgumentParser(description="星图寻迹桌面版")
    parser.add_argument("--server-only", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--host", default="127.0.0.1", help=argparse.SUPPRESS)
    parser.add_argument("--port", type=int, default=8765, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.server_only:
        _run_server_only(args.host, args.port)
    else:
        _run_desktop()


if __name__ == "__main__":
    main()
