# -*- mode: python ; coding: utf-8 -*-

import json
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files


project_root = Path(SPECPATH)
webview_datas, webview_binaries, webview_hiddenimports = collect_all("webview")
tetra3_datas = collect_data_files("tetra3", include_py_files=False)

datas = [
    (str(project_root / "frontend" / "dist"), "frontend/dist"),
    (str(project_root / "README.md"), "."),
] + webview_datas + tetra3_datas

backend_data_root = project_root / "backend" / "data"
nasa_manifest = json.loads((backend_data_root / "nasa_deep_sky.json").read_text(encoding="utf-8"))
referenced_nasa_images = {
    item["thumbnailFile"]
    for item in nasa_manifest["objects"].values()
    if isinstance(item, dict) and isinstance(item.get("thumbnailFile"), str)
}
for source in backend_data_root.rglob("*"):
    if not source.is_file():
        continue
    if (
        source.parent == backend_data_root / "nasa-deep-sky" / "images"
        and source.name not in referenced_nasa_images
    ):
        continue
    destination = source.parent.relative_to(project_root).as_posix()
    datas.append((str(source), destination))

hiddenimports = webview_hiddenimports + [
    "clr",
    "pythonnet",
    "scipy.ndimage",
    "scipy.optimize",
    "scipy.stats",
    "scipy.spatial",
    "scipy.spatial.distance",
    "PIL.JpegImagePlugin",
    "PIL.PngImagePlugin",
    "PIL.TiffImagePlugin",
    "PIL.WebPImagePlugin",
    "tetra3",
    "tetra3.tetra3",
]

a = Analysis(
    [str(project_root / "desktop_app.py")],
    pathex=[str(project_root)],
    binaries=webview_binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PyQt5", "PyQt6", "PySide2", "PySide6", "cefpython3", "gi"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="星图寻迹",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_root / "packaging" / "starfield-atlas.ico"),
    version=str(project_root / "packaging" / "windows_version_info.txt"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="星图寻迹",
)
