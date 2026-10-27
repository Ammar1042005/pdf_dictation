# Build: pyinstaller --noconfirm packaging/pdfdictation.spec   (run on each target OS)
# For protected build: First run pyarmor gen --recursive pdf_dictation, then this spec
from PyInstaller.utils.hooks import collect_submodules, collect_data_files, collect_dynamic_libs

# Collect all submodules to ensure no features are lost
hidden_imports = collect_submodules("pyttsx3") + collect_submodules("pdf_dictation")
hidden_imports += collect_submodules("pymupdf")
# Note: PySide6 is handled by PyInstaller's built-in hooks

# Collect data files for any packages that have them
datas = collect_data_files("pyttsx3")
datas += [("../pdf_dictation/assets", "pdf_dictation/assets")]
datas += [("../LICENSE", ".")]

# Collect dynamic libraries
binaries = collect_dynamic_libs("pyttsx3")

a = Analysis(
    ["../app.py"],
    pathex=[".."],
    datas=datas,
    binaries=binaries,
    hiddenimports=hidden_imports,
    hookspath=["packaging"],
    excludes=[
        "tkinter",
        "PySide6.QtWebEngineCore",
        "PySide6.QtQuick",
        "PySide6.QtQml",
        "PySide6.Qt3DCore",
        "matplotlib",
        "numpy",
        "pandas"
    ]
)

pyz = PYZ(a.pure)
# Single-file exe with all dependencies bundled - no features lost
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="PDFDictation",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None
)
