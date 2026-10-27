# PyInstaller hook for pymupdf (imported as fitz)
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Collect all submodules
hiddenimports = collect_submodules('pymupdf')

# Collect any data files
datas = collect_data_files('pymupdf')
