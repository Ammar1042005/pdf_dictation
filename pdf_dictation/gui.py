import sys
import logging
import pymupdf as fitz
import webbrowser
from PySide6.QtCore import QTimer, Qt, QThread, QRectF, Signal, QPoint, QSize
from PySide6.QtGui import QShortcut, QKeySequence, QPixmap, QImage, QPainter, QPen, QColor, QFont, QPalette, QIcon
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QFileDialog, QMessageBox, QDoubleSpinBox, QSpinBox, QProgressBar,
                               QProgressDialog, QLineEdit, QComboBox, QListWidget, QListWidgetItem, QSplitter,
                               QDialog, QTextEdit, QCheckBox)
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QScrollArea
from pdf_dictation import sessions, settings as cfg
from pdf_dictation.chunker import TextChunker, ImageItem, timing_char_count
from pdf_dictation.controller import Controller, State
from pdf_dictation.extractor import load_items, PdfError, search_document
from pdf_dictation.speech import SpeechEngine
from pdf_dictation.settings_dialog import SettingsDialog
from pdf_dictation import updater
from pdf_dictation import plugins

from pdf_dictation import paths
logging.basicConfig(filename=str(paths.log_file()), level=logging.INFO)
COLORS = {State.SPEAKING: "#1e88e5", State.WRITING: "#f9a825", State.IMAGE_PAUSED: "#e53935",
          State.PAUSED: "#757575", State.FINISHED: "#43a047", State.ERROR: "#c62828"}
LABELS = {State.SPEAKING: "🔊 SPEAKING", State.WRITING: "✍ WRITING", State.IMAGE_PAUSED:
          "⏸ IMAGE DETECTED — press SPACE to continue", State.PAUSED: "⏸ PAUSED",
          State.FINISHED: "✓ FINISHED", State.READY: "READY", State.IDLE: "OPEN A PDF",
          State.ERROR: "❌ SPEECH ERROR"}


class PreviewLabel(QLabel):
    clicked = Signal(QPoint)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(event.position().toPoint())
        super().mousePressEvent(event)


class LicenseDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("License Agreement")
        self.setMinimumSize(600, 500)
        layout = QVBoxLayout(self)

        title = QLabel("PDF Dictation License Agreement")
        title_font = QFont(title.font())
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        layout.addWidget(QLabel("Please read and accept the license to continue:"))

        # Clickable GitHub link
        github_label = QLabel('<a href="https://github.com/Ammar1042005/pdf_dictation">Source code available at GitHub</a>')
        github_label.setTextInteractionFlags(Qt.TextBrowserInteraction)
        github_label.setOpenExternalLinks(True)
        layout.addWidget(github_label)

        self.license_text = QTextEdit()
        self.license_text.setReadOnly(True)
        self.license_text.setPlainText(self._load_license())
        layout.addWidget(self.license_text)

        self.accept_checkbox = QCheckBox("I have read and agree to the license terms")
        self.accept_checkbox.stateChanged.connect(self._on_checkbox_changed)
        layout.addWidget(self.accept_checkbox)

        button_box = QHBoxLayout()
        self.accept_button = QPushButton("Accept")
        self.accept_button.setEnabled(False)
        self.accept_button.clicked.connect(self.accept)
        self.reject_button = QPushButton("Decline")
        self.reject_button.clicked.connect(self.reject)
        button_box.addWidget(self.reject_button)
        button_box.addWidget(self.accept_button)
        layout.addLayout(button_box)

    def _load_license(self):
        try:
            license_file = paths.resource("LICENSE")
            if license_file.exists():
                return license_file.read_text(encoding="utf-8")
        except Exception:
            pass
        return "License file not found. Please visit https://github.com/Ammar1042005/pdf_dictation to view the license."

    def _on_checkbox_changed(self, state):
        self.accept_button.setEnabled(state == 2)  # 2 = Qt.Checked

    def is_accepted(self):
        return self.result() == QDialog.Accepted


class Loader(QThread):
    """Reads/OCRs the PDF off the GUI thread."""
    progress = Signal(int, int); done = Signal(object); failed = Signal(str)

    def __init__(self, path, s):
        super().__init__(); self.path, self.s = path, s

    def run(self):
        s = self.s

        def prog(i, n):
            if self.isInterruptionRequested(): raise PdfError("Loading cancelled.")
            self.progress.emit(i, n)
        try:
            self.done.emit(load_items(self.path, s.min_img_w, s.min_img_h, TextChunker(s.word_rules()),
                                      s.ocr_mode, s.ocr_language, prog, s.use_ocr_cache))
        except PdfError as e: self.failed.emit(str(e))
        except Exception as e: self.failed.emit(f"Unexpected error: {e}")


class Win(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle("PDF Dictation"); self.setMinimumSize(700, 500)
        self.setWindowIcon(QIcon(str(paths.resource("assets/pdf_dictation.svg"))))
        self.ctl = None; self.path = None; self.doc = None
        self.settings = cfg.load()
        if self.settings.enable_plugins:
            self.plugin_voices = plugins.load_enabled_voice_profiles()
        else:
            self.plugin_voices = []
        self.speech = SpeechEngine(); self.apply_speech(); self.pages = 0; self.zoom = 1.2
        self._preview_cache = {}
        self._thumbnail_cache = {}
        self._page_history = []
        self._history_index = -1
        self._history_navigation = False
        self._refreshing_preview = False
        self.bookmarks = []
        if self.settings.auto_update:
            QTimer.singleShot(1500, self.check_for_updates)
        w = QWidget(); self.setCentralWidget(w); root = QVBoxLayout(w)
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(4)
        top = QHBoxLayout(); b = QPushButton("Open PDF…"); b.clicked.connect(self.open_pdf); top.addWidget(b)
        sb = QPushButton("Settings…"); sb.clicked.connect(self.open_settings); top.addWidget(sb)
        self.spc = QDoubleSpinBox(); self.spc.setRange(0.05, 5); self.spc.setSingleStep(0.25)
        self.spc.setValue(self.settings.seconds_per_char); self.spc.valueChanged.connect(lambda v: setattr(self.settings, "seconds_per_char", v))
        self.extra = QDoubleSpinBox(); self.extra.setRange(0, 30); self.extra.setValue(self.settings.extra_pause)
        self.extra.valueChanged.connect(lambda v: setattr(self.settings, "extra_pause", v))
        for lab, sp in (("Sec/char", self.spc), ("Extra pause", self.extra)): top.addWidget(QLabel(lab)); top.addWidget(sp)
        root.addLayout(top)
        # Page navigation controls
        page_nav = QHBoxLayout()
        self.page_spin = QSpinBox(); self.page_spin.setRange(1, 9999); self.page_spin.valueChanged.connect(self.go_to_page)
        self.page_label = QLabel("Page:"); self.page_total = QLabel("/ 0")
        page_nav.addWidget(self.page_label); page_nav.addWidget(self.page_spin); page_nav.addWidget(self.page_total)
        go_page = QPushButton("Go"); go_page.clicked.connect(lambda: self.go_to_page(self.page_spin.value()))
        page_nav.addWidget(go_page)
        self.back_button = QPushButton("Back")
        self.back_button.clicked.connect(self.go_back)
        self.forward_button = QPushButton("Forward")
        self.forward_button.clicked.connect(self.go_forward)
        page_nav.addWidget(self.back_button); page_nav.addWidget(self.forward_button)
        # Zoom controls
        self.zoom_spin = QDoubleSpinBox(); self.zoom_spin.setRange(0.5, 3.0); self.zoom_spin.setSingleStep(0.1); self.zoom_spin.setDecimals(1)
        self.zoom_spin.setValue(self.zoom); self.zoom_spin.valueChanged.connect(self.set_zoom)
        page_nav.addWidget(QLabel("  Zoom:")); page_nav.addWidget(self.zoom_spin)
        zoom_out = QPushButton("-"); zoom_out.setToolTip("Zoom out"); zoom_out.clicked.connect(lambda: self.set_zoom(self.zoom - 0.1))
        zoom_in = QPushButton("+"); zoom_in.setToolTip("Zoom in"); zoom_in.clicked.connect(lambda: self.set_zoom(self.zoom + 0.1))
        page_nav.addWidget(zoom_out); page_nav.addWidget(zoom_in)
        self.search_text = QLineEdit(); self.search_text.setPlaceholderText("Search document…")
        self.search_text.returnPressed.connect(self.search_document)
        search_button = QPushButton("Search"); search_button.clicked.connect(self.search_document)
        self.search_results = QComboBox(); self.search_results.setMinimumWidth(260)
        self.search_results.activated.connect(self.open_search_result)
        page_nav.addWidget(self.search_text); page_nav.addWidget(search_button); page_nav.addWidget(self.search_results)
        self.bookmark_button = QPushButton("Bookmark page"); self.bookmark_button.clicked.connect(self.toggle_bookmark)
        page_nav.addWidget(self.bookmark_button)
        page_nav.addStretch()
        root.addLayout(page_nav)
        self.bookmark_list = QListWidget()
        self.bookmark_list.setMaximumHeight(70)
        self.bookmark_list.setVisible(False)
        self.bookmark_list.itemActivated.connect(self.open_bookmark)
        root.addWidget(self.bookmark_list)
        self.view = PreviewLabel(alignment=Qt.AlignTop | Qt.AlignLeft)
        self.view.clicked.connect(self.select_at_preview_position)
        self.view.setMinimumSize(1, 1)
        self.preview = QScrollArea()
        self.preview.setWidget(self.view)
        self.preview.setWidgetResizable(False)
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.horizontalScrollBar().valueChanged.connect(self._refresh_visible_preview)
        self.preview.verticalScrollBar().valueChanged.connect(self._refresh_visible_preview)
        self.thumbnail_list = QListWidget()
        self.thumbnail_list.setViewMode(QListWidget.ListMode)
        self.thumbnail_list.setIconSize(QSize(120, 160))
        self.thumbnail_list.setMinimumWidth(155)
        self.thumbnail_list.setMaximumWidth(220)
        self.thumbnail_list.itemClicked.connect(self.open_thumbnail)
        self.thumbnail_list.setAccessibleName("Page thumbnails")
        self.thumbnail_list.setAccessibleDescription("Scrollable list of PDF pages. Select a page to preview it.")
        preview_splitter = QSplitter(Qt.Horizontal)
        preview_splitter.addWidget(self.thumbnail_list)
        preview_splitter.addWidget(self.preview)
        preview_splitter.setStretchFactor(1, 1)
        root.addWidget(preview_splitter, 1)
        self.status = QLabel("OPEN A PDF", alignment=Qt.AlignCenter)
        status_font = QFont(self.status.font()); status_font.setPointSize(20); status_font.setBold(True)
        self.status.setFont(status_font); self.status.setStyleSheet("padding:4px")
        self.chunk = QLabel("", alignment=Qt.AlignCenter, wordWrap=True)
        chunk_font = QFont(self.chunk.font()); chunk_font.setPointSize(16)
        self.chunk.setFont(chunk_font)
        self.info = QLabel("")
        info_font = QFont(self.info.font()); info_font.setPointSize(9)
        self.info.setFont(info_font)
        self.bar = QProgressBar(); self.bar.setRange(0, 1000); self.bar.setMaximumHeight(10)
        for widget, name, description in (
            (self.status, "Dictation status", "Current dictation state and speech status."),
            (self.chunk, "Current dictation chunk", "Text currently being spoken or copied."),
            (self.info, "Document position", "Current page and dictation item position."),
            (self.bar, "Writing progress", "Progress through the current writing interval."),
        ):
            widget.setAccessibleName(name)
            widget.setAccessibleDescription(description)
        for x in (self.status, self.chunk, self.info, self.bar): root.addWidget(x)
        # On-screen control buttons
        btn_layout = QHBoxLayout()
        self.btn_start = QPushButton("Start"); self.btn_start.clicked.connect(self.on_start_pause)
        self.btn_repeat = QPushButton("Repeat"); self.btn_repeat.clicked.connect(self.on_repeat)
        self.btn_prev = QPushButton("Previous"); self.btn_prev.clicked.connect(self.on_prev)
        self.btn_next = QPushButton("Next"); self.btn_next.clicked.connect(self.on_next)
        for btn in (self.btn_start, self.btn_repeat, self.btn_prev, self.btn_next):
            btn.setMinimumWidth(100); btn_layout.addWidget(btn)
        root.addLayout(btn_layout)
        controls = (
            (b, "Open PDF", "Open a PDF document for dictation."),
            (sb, "Settings", "Configure speech, OCR, chunking, and writing-time settings."),
            (self.page_spin, "Page number", "Enter the page number to preview."),
            (go_page, "Go to page", "Show the selected page."),
            (self.back_button, "Back", "Return to the previous visited page."),
            (self.forward_button, "Forward", "Return to the next page in navigation history."),
            (self.zoom_spin, "Zoom level", "Set preview zoom from 0.5 to 3.0."),
            (zoom_out, "Zoom out", "Decrease preview zoom."),
            (zoom_in, "Zoom in", "Increase preview zoom."),
            (self.search_text, "Search document", "Enter text to search across the document."),
            (search_button, "Search", "Search the document."),
            (self.search_results, "Search results", "Select a matching search result."),
            (self.bookmark_button, "Bookmark page", "Add or remove a bookmark for the current page."),
            (self.bookmark_list, "Bookmarks", "Pages bookmarked in the current document."),
            (self.view, "PDF preview", "Scrollable PDF preview. Click text to select a dictation chunk."),
            (self.btn_start, "Start or pause", "Start, pause, or resume dictation."),
            (self.btn_repeat, "Repeat chunk", "Repeat the current spoken chunk."),
            (self.btn_prev, "Previous item", "Move to the previous dictation item."),
            (self.btn_next, "Next item", "Move to the next dictation item."),
        )
        for widget, name, description in controls:
            widget.setAccessibleName(name)
            widget.setAccessibleDescription(description)
        for first, second in zip(
            (b, sb, self.page_spin, go_page, self.zoom_spin, zoom_out, zoom_in, self.search_text,
             search_button, self.search_results, self.bookmark_button, self.bookmark_list, self.btn_start,
             self.btn_repeat, self.btn_prev),
            (sb, self.page_spin, go_page, self.zoom_spin, zoom_out, zoom_in, self.search_text, search_button,
             self.search_results, self.bookmark_button, self.bookmark_list, self.btn_start, self.btn_repeat,
             self.btn_prev, self.btn_next),
        ):
            self.setTabOrder(first, second)
        self._update_history_buttons()
        for key, fn in (("Space", "toggle"), ("R", "repeat"), ("Left", "prev"), ("Right", "next"), ("Esc", "stop"), ("F", "repeat")):
            sc = QShortcut(QKeySequence(key), self); sc.setContext(Qt.ApplicationShortcut)
            sc.activated.connect(lambda f=fn: self.ctl and getattr(self.ctl, f)())
        # +/- for speech rate adjustment
        for key, delta in (("+", 10), ("-", -10)):
            sc = QShortcut(QKeySequence(key), self); sc.setContext(Qt.ApplicationShortcut)
            sc.activated.connect(lambda d=delta: self.adjust_rate(d))
        t = QTimer(self); t.timeout.connect(self.tick); t.start(100)

    def open_pdf(self):
        p, _ = QFileDialog.getOpenFileName(self, "PDF", "", "PDF (*.pdf)")
        if not p: return
        self.stop_loader()
        dlg = QProgressDialog("Reading PDF (scanned pages are OCR'd, this can take a while)…", "Cancel", 0, 100, self)
        dlg.setWindowModality(Qt.WindowModal); dlg.setMinimumDuration(500)
        self.loader = Loader(p, self.settings)
        self.loader.progress.connect(lambda i, n: (dlg.setMaximum(n), dlg.setValue(i)))
        self.loader.failed.connect(lambda m: (dlg.close(), QMessageBox.critical(self, "Error", m)))
        self.loader.done.connect(lambda res: (dlg.close(), self.on_loaded(p, res)))
        dlg.canceled.connect(self.loader.requestInterruption)
        self.loader.start()

    def on_loaded(self, p, res):
        if self.doc: self.doc.close()
        self._preview_cache.clear()
        self._thumbnail_cache.clear()
        self.pages, self.doc, self.path = res.pages, fitz.open(p), p
        self.bookmarks = []
        self.bookmark_list.clear()
        self.search_results.clear()
        self.page_spin.setRange(1, self.pages); self.page_total.setText(f"/ {self.pages}")
        self._page_history = []
        self._history_index = -1
        self._update_history_buttons()
        self.populate_thumbnails()
        if res.ocr_pages:
            QMessageBox.information(self, "OCR used", f"{res.ocr_pages} scanned page(s) were read with OCR. "
                                    "Accuracy depends on scan quality; check the preview if a chunk sounds wrong.")
        if res.warnings:
            QMessageBox.warning(self, "PDF loading warnings", "\n".join(res.warnings))
        self.ctl = Controller(res.items, self.speech, self.settings, on_change=self.refresh)
        s = sessions.load(p)
        if s and QMessageBox.question(self, "Resume", "Resume from previous position?") == QMessageBox.Yes:
            index = min(s["chunk_index"], len(res.items) - 1)
            saved_hash = s.get("chunk_text_hash")
            if saved_hash:
                for candidate, item in enumerate(res.items):
                    if not isinstance(item, ImageItem) and sessions.text_hash(item.text) == saved_hash:
                        index = candidate
                        break
            self.ctl.index = index
        self.refresh()

    def tick(self):
        if not self.ctl: return
        self.ctl.tick()
        if self.ctl.state == State.WRITING:
            chars = timing_char_count(self.ctl.item.text, self.settings.writing_profile)
            tot = max(0.001, chars * self.settings.seconds_per_char + self.settings.extra_pause)
            self.bar.setValue(int(1000 * (1 - self.ctl.time_left() / tot)))
            self.status.setText(f"✍ WRITING  {self.ctl.time_left():.1f}s")

    def refresh(self):
        c = self.ctl; st = c.state; it = c.item
        self.status.setText(LABELS[st]); self._style_status(st)
        if st == State.ERROR:
            self.chunk.setText(f"Error: {self.speech.last_error}")
            self.info.setText("")
        elif it is not None:
            self.chunk.setText("[IMAGE]" if isinstance(it, ImageItem) else it.text)
            self.info.setText(f"Page {it.page_number} / {self.pages}   Item {c.index + 1} / {len(c.items)}"
                              + ("" if isinstance(it, ImageItem) else f"   Writing time: {c.remaining or 0:.2f}s"))
            self.show_page(it)
            # Sync page spinner with current chunk's page
            if self.page_spin.value() != it.page_number:
                self.page_spin.blockSignals(True)
                self.page_spin.setValue(it.page_number)
                self.page_spin.blockSignals(False)
        if self.path:
            item_text = None if isinstance(it, ImageItem) or it is None else it.text
            sessions.save(
                self.path, c.index, {"seconds_per_character": self.settings.seconds_per_char},
                page_number=None if it is None else it.page_number,
                chunk_text=item_text,
                extraction_settings={
                    "target": self.settings.target,
                    "short_weight": self.settings.short_weight,
                    "long_weight": self.settings.long_weight,
                    "short_max": self.settings.short_max,
                },
            )
        # Update button states
        self.btn_start.setText("Pause" if st in (State.SPEAKING, State.WRITING) else "Resume" if st == State.PAUSED else "Start")
        self.btn_start.setEnabled(self.ctl is not None and st != State.IDLE and st != State.FINISHED and st != State.ERROR)
        self.btn_repeat.setEnabled(self.ctl is not None and st != State.IDLE and st != State.FINISHED and st != State.ERROR and not isinstance(it, ImageItem))
        self.btn_prev.setEnabled(self.ctl is not None and c.index > 0)
        self.btn_next.setEnabled(self.ctl is not None and c.index < len(c.items) - 1)

    def apply_speech(self):
        s = self.settings; self.speech.rate, self.speech.volume, self.speech.voice_id = s.rate, s.volume, s.voice_id or None

    def open_settings(self):
        extra_voices = self.plugin_voices if self.settings.enable_plugins else ()
        d = SettingsDialog(self.settings, self.speech.voices(extra_voices), self)
        if d.exec():
            for k, v in vars(d.result_settings()).items(): setattr(self.settings, k, v)  # in place: controller sees it
            cfg.save(self.settings); self.apply_speech()

    def check_for_updates(self):
        try:
            release = updater.check_latest_sources(__import__("pdf_dictation").__version__)
        except RuntimeError as exc:
            logging.getLogger("pdf_dictation").warning("%s", exc)
            return
        if release:
            answer = QMessageBox.question(
                self, "Update available",
                f"{release.name} is available. Open the GitHub release page?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if answer == QMessageBox.Yes:
                webbrowser.open(release.url)
            self.spc.setValue(self.settings.seconds_per_char); self.extra.setValue(self.settings.extra_pause)

    def show_page(self, it, highlight=True):
        if not self.doc: return
        if self._refreshing_preview:
            return
        self._refreshing_preview = True
        page, z = self.doc[it.page_number - 1], self.zoom
        try:
            pm = self._visible_page_pixmap(it.page_number, z)
            if highlight:
                p = QPainter(pm)
                if isinstance(it, ImageItem):
                    p.setPen(QPen(QColor("#e53935"), 5)); rects = [it.bbox]
                else:
                    p.setPen(Qt.NoPen); p.setBrush(QColor(255, 235, 59, 120))
                    if it.word_bboxes:
                        found = [tuple(rect) for rect, _ in it.word_bboxes]
                    else:
                        try: found = [tuple(r) for r in page.search_for(it.text) if fitz.Rect(r).intersects(fitz.Rect(it.bbox))] if it.bbox else []
                        except Exception: found = []
                    rects = found or ([it.bbox] if it.bbox else [])
                for r in rects: p.drawRect(QRectF(r[0] * z, r[1] * z, (r[2] - r[0]) * z, (r[3] - r[1]) * z))
                p.end()
            self.view.setPixmap(pm)
            self.view.adjustSize()
        finally:
            self._refreshing_preview = False

    def _page_pixmap(self, page_number, zoom):
        key = (page_number, round(zoom, 2))
        cached = self._preview_cache.get(key)
        if cached is not None:
            return cached
        page = self.doc[page_number - 1]
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        image = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888).copy()
        cached = QPixmap.fromImage(image)
        self._preview_cache[key] = cached
        return cached

    def _visible_page_pixmap(self, page_number, zoom):
        """Rasterize only the visible page region, retaining a full scroll canvas."""
        page = self.doc[page_number - 1]
        canvas_size = page.rect * zoom
        canvas = QPixmap(int(canvas_size.width), int(canvas_size.height))
        canvas.fill(Qt.white)
        viewport = self.preview.viewport().size()
        left = max(0, self.preview.horizontalScrollBar().value() - viewport.width())
        top = max(0, self.preview.verticalScrollBar().value() - viewport.height())
        right = min(canvas.width(), self.preview.horizontalScrollBar().value() + viewport.width() * 2)
        bottom = min(canvas.height(), self.preview.verticalScrollBar().value() + viewport.height() * 2)
        clip = fitz.Rect(left / zoom, top / zoom, right / zoom, bottom / zoom)
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=clip, alpha=False)
        region = QPixmap.fromImage(QImage(
            pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888
        ).copy())
        painter = QPainter(canvas)
        painter.drawPixmap(int(clip.x0 * zoom), int(clip.y0 * zoom), region)
        painter.end()
        return canvas

    def _refresh_visible_preview(self):
        if not self._refreshing_preview and self.doc and self.ctl and self.ctl.item:
            self.show_page(self.ctl.item)

    def on_start_pause(self):
        if self.ctl: self.ctl.toggle()

    def on_repeat(self):
        if self.ctl: self.ctl.repeat()

    def on_prev(self):
        if self.ctl: self.ctl.prev()

    def on_next(self):
        if self.ctl: self.ctl.next()

    def adjust_rate(self, delta):
        new_rate = max(60, min(350, self.settings.rate + delta))
        if new_rate != self.settings.rate:
            self.settings.rate = new_rate
            self.apply_speech()
            cfg.save(self.settings)

    def go_to_page(self, page_num):
        if not self.doc or page_num < 1 or page_num > self.pages: return
        if not self._history_navigation:
            if not self._page_history or self._page_history[self._history_index] != page_num:
                self._page_history = self._page_history[:self._history_index + 1]
                self._page_history.append(page_num)
                self._history_index = len(self._page_history) - 1
        pm = self._page_pixmap(page_num, self.zoom)
        self.view.setPixmap(pm)
        self.view.adjustSize()
        for index in range(self.thumbnail_list.count()):
            item = self.thumbnail_list.item(index)
            if item.data(Qt.UserRole) == page_num:
                self.thumbnail_list.setCurrentItem(item)
                break
        self._refresh_bookmarks()
        self._update_history_buttons()

    def _update_history_buttons(self):
        self.back_button.setEnabled(self._history_index > 0)
        self.forward_button.setEnabled(
            0 <= self._history_index < len(self._page_history) - 1
        )

    def _visit_history_index(self, index):
        if index < 0 or index >= len(self._page_history):
            return
        self._history_navigation = True
        try:
            self.page_spin.setValue(self._page_history[index])
            self.go_to_page(self._page_history[index])
            self._history_index = index
        finally:
            self._history_navigation = False
        self._update_history_buttons()

    def go_back(self):
        self._visit_history_index(self._history_index - 1)

    def go_forward(self):
        self._visit_history_index(self._history_index + 1)

    def populate_thumbnails(self):
        self.thumbnail_list.clear()
        if not self.doc:
            return
        for page_number in range(1, self.pages + 1):
            thumbnail = self._thumbnail_pixmap(page_number)
            item = QListWidgetItem(QIcon(thumbnail), f"Page {page_number}")
            item.setData(Qt.UserRole, page_number)
            self.thumbnail_list.addItem(item)

    def _thumbnail_pixmap(self, page_number):
        cached = self._thumbnail_cache.get(page_number)
        if cached is not None:
            return cached
        page = self.doc[page_number - 1]
        pix = page.get_pixmap(matrix=fitz.Matrix(0.2, 0.2), alpha=False)
        image = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888).copy()
        thumbnail = QPixmap.fromImage(image)
        self._thumbnail_cache[page_number] = thumbnail
        return thumbnail

    def open_thumbnail(self, item):
        page_number = item.data(Qt.UserRole)
        if page_number is not None:
            self.page_spin.setValue(page_number)
            self.go_to_page(page_number)

    def search_document(self):
        if not self.doc:
            return
        matches = search_document(self.doc, self.search_text.text())
        self.search_results.clear()
        for page_number, rect in matches:
            self.search_results.addItem(f"Page {page_number} ({rect[0]:.0f}, {rect[1]:.0f})", (page_number, rect))
        if matches:
            self.open_search_result(0)

    def open_search_result(self, index):
        if index < 0:
            return
        result = self.search_results.itemData(index)
        if result:
            self.page_spin.setValue(result[0])
            self.go_to_page(result[0])

    def toggle_bookmark(self):
        if not self.doc or not self.pages:
            return
        page = self.page_spin.value()
        if page in self.bookmarks:
            self.bookmarks.remove(page)
        else:
            self.bookmarks.append(page)
            self.bookmarks.sort()
        self._refresh_bookmarks()

    def _refresh_bookmarks(self):
        self.bookmark_list.clear()
        for page in self.bookmarks:
            self.bookmark_list.addItem(QListWidgetItem(f"Page {page}"))
        self.bookmark_list.setVisible(bool(self.bookmarks))
        current = self.page_spin.value()
        self.bookmark_button.setText("Remove bookmark" if current in self.bookmarks else "Bookmark page")

    def open_bookmark(self, item):
        try:
            page = int(item.text().split()[1])
        except (IndexError, ValueError):
            return
        self.page_spin.setValue(page)
        self.go_to_page(page)

    def set_zoom(self, zoom_level):
        self.zoom = max(self.zoom_spin.minimum(), min(self.zoom_spin.maximum(), zoom_level))
        if self.zoom_spin.value() != self.zoom:
            self.zoom_spin.blockSignals(True)
            self.zoom_spin.setValue(self.zoom)
            self.zoom_spin.blockSignals(False)
        if self.ctl and self.ctl.item:
            self.show_page(self.ctl.item)
        elif self.doc and self.page_spin.value() <= self.pages:
            self.go_to_page(self.page_spin.value())

    def stop_loader(self):
        loader = getattr(self, "loader", None)
        if loader and loader.isRunning():
            loader.requestInterruption()
            loader.wait(5000)

    def closeEvent(self, event):
        self.stop_loader()
        self.speech.stop()
        if self.doc:
            self.doc.close()
        self._preview_cache.clear()
        self._thumbnail_cache.clear()
        self.doc = None
        event.accept()

    def select_at_preview_position(self, position):
        if not self.doc or not self.ctl:
            return
        page_number = self.page_spin.value()
        page = self.doc[page_number - 1]
        point = fitz.Point(position.x() / self.zoom, position.y() / self.zoom)
        for index, item in enumerate(self.ctl.items):
            if item.page_number != page_number or isinstance(item, ImageItem):
                continue
            if item.word_bboxes:
                words = {word.casefold().strip(".,;:!?()[]{}") for word in item.words}
                if any(
                    fitz.Rect(rect).contains(point)
                    and text.casefold().strip(".,;:!?()[]{}") in words
                    for rect, text in item.word_bboxes
                ):
                    self._select_item(index)
                    return
            try:
                rects = page.search_for(item.text)
            except Exception:
                rects = []
            if any(fitz.Rect(rect).contains(point) for rect in rects):
                self._select_item(index)
                return
            if item.bbox and fitz.Rect(item.bbox).contains(point):
                self._select_item(index)
                return

    def _style_status(self, state):
        palette = QApplication.palette()
        background = QColor(palette.color(QPalette.Window))
        foreground = QColor(palette.color(QPalette.WindowText))
        contrast = max(background.lightness(), foreground.lightness()) - min(
            background.lightness(), foreground.lightness()
        )
        if contrast > 180:
            bg = palette.color(QPalette.Highlight).name()
            fg = palette.color(QPalette.HighlightedText).name()
        else:
            bg = COLORS.get(state, "#455a64")
            fg = "white"
        self.status.setStyleSheet(f"padding:4px;color:{fg};background:{bg}")

    def _select_item(self, index):
        self.speech.stop()
        self.ctl.index = index
        self.ctl.remaining = 0.0
        self.ctl._paused_from = None
        self.ctl._set(State.PAUSED)


def main():
    a = QApplication(sys.argv)
    a.setApplicationName("PDF Dictation")
    a.setWindowIcon(QIcon(str(paths.resource("assets/pdf_dictation.svg"))))

    settings = cfg.load()

    if not settings.license_accepted:
        dialog = LicenseDialog()
        if dialog.exec() == QDialog.Accepted:
            settings.license_accepted = True
            cfg.save(settings)
        else:
            QMessageBox.warning(None, "License Required", "You must accept the license to use PDF Dictation.")
            sys.exit(1)

    w = Win()
    w.resize(900, 800)
    w.show()
    sys.exit(a.exec())


if __name__ == "__main__":
    main()
