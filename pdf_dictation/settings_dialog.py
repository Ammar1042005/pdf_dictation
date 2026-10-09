import sys
from dataclasses import replace
from PySide6.QtWidgets import (QDialog, QFormLayout, QDialogButtonBox, QDoubleSpinBox, QSpinBox, QCheckBox,
                               QComboBox, QLineEdit, QPushButton, QLabel, QVBoxLayout, QMessageBox, QInputDialog,
                               QFileDialog, QScrollArea, QWidget)
from pdf_dictation.speech import SpeechEngine
from pdf_dictation import sessions, diagnostics
from pdf_dictation.chunker import timing_char_count
from pdf_dictation import plugins


def _dspin(lo, hi, v, step=0.25):
    w = QDoubleSpinBox(); w.setRange(lo, hi); w.setSingleStep(step); w.setDecimals(2); w.setValue(v); return w


class SettingsDialog(QDialog):
    def __init__(self, s, voices, parent=None):
        super().__init__(parent); self.setWindowTitle("Settings"); self.s = s
        f = QFormLayout()
        self.spc = _dspin(0.05, 5, s.seconds_per_char); self.extra = _dspin(0, 30, s.extra_pause, 1)
        self.profile_timing = QComboBox(); self.profile_timing.addItems(["prose", "code", "equations", "custom"])
        self.profile_timing.setCurrentText(s.writing_profile)
        calibrate = QPushButton("Calibrate handwriting speed"); calibrate.clicked.connect(self.calibrate)
        self.target = _dspin(1, 10, s.target, 0.5); self.sw = _dspin(0, 5, s.short_weight, 0.25)
        self.lw = _dspin(0, 5, s.long_weight, 0.25)
        self.smax = QSpinBox(); self.smax.setRange(1, 10); self.smax.setValue(s.short_max)
        self.voice = QComboBox(); self.voice.addItem("System default", "")
        for vid, name in voices: self.voice.addItem(name, vid)
        i = self.voice.findData(s.voice_id); self.voice.setCurrentIndex(max(i, 0))
        self.voice_status = QLabel(
            f"pyttsx3 backend: {len(voices)} voice(s) detected"
            + ("; saved voice is unavailable" if s.voice_id and i < 0 else "")
        )
        self.rate = QSpinBox(); self.rate.setRange(60, 350); self.rate.setValue(s.rate)
        self.vol = _dspin(0, 1, s.volume, 0.1)
        test = QPushButton("Test Voice"); test.clicked.connect(self.test_voice)
        self.pimg = QCheckBox("Pause at images"); self.pimg.setChecked(s.pause_at_images)
        self.iw = QSpinBox(); self.iw.setRange(0, 2000); self.iw.setValue(s.min_img_w)
        self.ih = QSpinBox(); self.ih.setRange(0, 2000); self.ih.setValue(s.min_img_h)
        self.punct = QCheckBox("Speak punctuation"); self.punct.setChecked(s.speak_punctuation)
        self.symbols = QCheckBox("Speak code symbols"); self.symbols.setChecked(s.speak_symbols)
        self.profile = QComboBox(); self.profile.addItems(["automatic", "prose", "code"])
        self.profile.setCurrentText(s.speech_profile)
        self.norm = QCheckBox("Normalize abbreviations/numbers"); self.norm.setChecked(s.normalize)
        self.ocr = QComboBox(); self.ocr.addItems(["auto", "off"]); self.ocr.setCurrentText(s.ocr_mode)
        self.ocrlang = QLineEdit(s.ocr_language)
        self.cache = QCheckBox("Cache OCR results"); self.cache.setChecked(s.use_ocr_cache)
        clear_cache = QPushButton("Clear OCR Cache"); clear_cache.clicked.connect(self.clear_ocr_cache)
        export_diagnostics = QPushButton("Export Privacy-Safe Diagnostics")
        export_diagnostics.clicked.connect(self.export_diagnostics)
        self.auto_update = QCheckBox("Check GitHub for updates at startup")
        self.auto_update.setChecked(s.auto_update)
        self.enable_plugins = QCheckBox("Enable external plugins and voice profiles")
        self.enable_plugins.setChecked(s.enable_plugins)
        open_plugins = QPushButton("Open plugins folder")
        open_plugins.clicked.connect(self.open_plugins_folder)
        for lab, w in (("OCR for scanned pages", self.ocr), ("OCR language (e.g. eng, hin)", self.ocrlang),
                       ("", self.cache), ("", clear_cache), ("", export_diagnostics),
                       ("Target word-units per chunk", self.target), ("Seconds per character", self.spc),
                       ("Extra pause (s)", self.extra), ("Writing-time profile", self.profile_timing),
                       ("", calibrate), ("Short word weight", self.sw), ("Long word weight", self.lw),
                       ("Short word max letters", self.smax), ("Voice", self.voice), ("", self.voice_status),
                       ("Speech rate", self.rate),
                       ("Volume", self.vol), ("", test), ("", self.pimg), ("Min image width", self.iw),
                       ("Min image height", self.ih), ("Speech profile", self.profile), ("", self.punct),
                       ("", self.symbols), ("", self.norm)): f.addRow(lab, w)
        f.addRow("", self.auto_update)
        f.addRow("", self.enable_plugins)
        f.addRow("", open_plugins)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        note = QLabel("Chunk and image settings apply the next time a PDF is opened."); note.setWordWrap(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.addLayout(f)
        content_layout.addWidget(note)
        content_layout.addWidget(bb)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumSize(420, 260)
        scroll.setSizeAdjustPolicy(QScrollArea.AdjustIgnored)
        scroll.setWidget(content)
        scroll.setAccessibleName("Settings form")
        scroll.setAccessibleDescription("Scrollable PDF Dictation settings form.")
        lay = QVBoxLayout(self)
        lay.addWidget(scroll)
        screen = self.screen()
        if screen:
            available = screen.availableGeometry()
            self.resize(min(650, available.width()), min(800, available.height()))
        self.setMinimumSize(460, 300)
        self.setSizeGripEnabled(True)

    def result_settings(self):
        return replace(self.s, seconds_per_char=self.spc.value(), extra_pause=self.extra.value(),
                       writing_profile=self.profile_timing.currentText(),
                       target=self.target.value(), short_weight=self.sw.value(), long_weight=self.lw.value(),
                       short_max=self.smax.value(), voice_id=self.voice.currentData() or "", rate=self.rate.value(),
                       volume=self.vol.value(), pause_at_images=self.pimg.isChecked(), min_img_w=self.iw.value(),
                       min_img_h=self.ih.value(), speak_punctuation=self.punct.isChecked(),
                       normalize=self.norm.isChecked(), speak_symbols=self.symbols.isChecked(),
                       speech_profile=self.profile.currentText(),
                       ocr_mode=self.ocr.currentText(),
                       ocr_language=self.ocrlang.text().strip() or "eng", use_ocr_cache=self.cache.isChecked(),
                       auto_update=self.auto_update.isChecked(),
                       enable_plugins=self.enable_plugins.isChecked())

    def open_plugins_folder(self):
        import os
        import subprocess
        folder = str(plugins.directory())
        if hasattr(os, "startfile"):
            os.startfile(folder)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", folder])
        else:
            subprocess.Popen(["xdg-open", folder])

    def calibrate(self):
        sample = "The quick brown fox writes this sample sentence for calibration."
        count = timing_char_count(sample, "prose")
        seconds, ok = QInputDialog.getDouble(
            self, "Handwriting calibration",
            f"Write this sample, then enter the elapsed seconds:\n\n{sample}\n\n"
            f"({count} alphanumeric characters)",
            max(1.0, count * self.spc.value()), 1.0, 600.0, 1,
        )
        if ok:
            self.spc.setValue(max(0.05, min(5.0, seconds / count)))
            self.profile_timing.setCurrentText("custom")

    def test_voice(self):
        r = self.result_settings()
        self._tmp = SpeechEngine(r.rate, r.volume, r.voice_id or None); self._tmp.speak("This is a test of the selected voice.")

    def clear_ocr_cache(self):
        if QMessageBox.question(self, "Clear OCR Cache",
                                 "This will delete all cached OCR results. Re-opening scanned PDFs will be slower. Continue?",
                                 QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            sessions.clear_ocr_cache()
            QMessageBox.information(self, "Cache Cleared", "OCR cache has been cleared.")

    def export_diagnostics(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export diagnostics", "pdfdictation-diagnostics.json", "JSON (*.json)"
        )
        if not path:
            return
        try:
            diagnostics.write_report(path, self.result_settings())
        except OSError as ex:
            QMessageBox.critical(self, "Diagnostics export failed", str(ex))
        else:
            QMessageBox.information(
                self, "Diagnostics exported",
                "The report contains settings and environment information only; document text is not included.",
            )
