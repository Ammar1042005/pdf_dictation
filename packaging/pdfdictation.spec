# Build: pyinstaller --noconfirm packaging/pdfdictation.spec   (run on each target OS)
from PyInstaller.utils.hooks import collect_submodules
hidden = collect_submodules("pyttsx3") + collect_submodules("pdf_dictation")
a = Analysis(["../app.py"], pathex=[".."], datas=[("../pdf_dictation/assets", "pdf_dictation/assets")],
             hiddenimports=hidden,
             excludes=["tkinter", "PySide6.QtWebEngineCore", "PySide6.QtQuick", "PySide6.QtQml", "PySide6.Qt3DCore"])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="PDFDictation", console=False)
coll = COLLECT(exe, a.binaries, a.datas, name="PDFDictation")
