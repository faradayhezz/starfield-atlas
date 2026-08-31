from __future__ import annotations

import os
import sys
from pathlib import Path


APP_NAME = "星图寻迹"
RESOURCE_ROOT = Path(__file__).resolve().parents[1]


def _user_data_root() -> Path:
    override = os.environ.get("STARFIELD_ATLAS_USER_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    if getattr(sys, "frozen", False):
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / APP_NAME
        return Path.home() / "AppData" / "Local" / APP_NAME
    return RESOURCE_ROOT / ".runtime"


USER_DATA_ROOT = _user_data_root()
JOBS_DIR = USER_DATA_ROOT / "jobs"
SKY_MAP_CACHE_DIR = USER_DATA_ROOT / "sky-map-cache"
HIPS_CACHE_DIR = USER_DATA_ROOT / "sky-map-hips"
WEBVIEW_DATA_DIR = USER_DATA_ROOT / "webview"
LOG_DIR = USER_DATA_ROOT / "logs"
