# Single-file, console-free Windows build. Run with python src/main.py --build.
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

root = Path(SPECPATH).resolve().parent
a = Analysis(
    [str(root / 'src' / 'main.py')],
    pathex=[str(root)],
    binaries=[],
    datas=[(str(root / 'resource'), 'resource'),
           (str(root / 'src' / 'config' / 'gamani-jjom.prod.cfg.json'), 'src/config')],
    hiddenimports=collect_submodules('src'),
    hookspath=[],
    runtime_hooks=[str(root / 'packaging' / 'windowed_runtime.py')],
    excludes=['PyQt5', 'PyQt6', 'PySide2', 'tkinter', 'pytest'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name='GamaniJJom',
    debug=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon=str(root / 'resource' / 'app.ico'),
    uac_admin=False,
)
