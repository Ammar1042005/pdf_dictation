import pytest

pytest.importorskip("PySide6")
fitz = pytest.importorskip("pymupdf")

from PySide6.QtWidgets import QApplication
from pdf_dictation.gui import Win


@pytest.fixture(name="_app")
def qt_app():
    instance = QApplication.instance() or QApplication([])
    yield instance
    instance.processEvents()


def test_gui_search_and_bookmark_navigation(tmp_path, _app):
    _ = _app
    path = tmp_path / "gui.pdf"
    doc = fitz.open()
    doc.new_page().insert_text((50, 50), "first page")
    doc.new_page().insert_text((50, 50), "target phrase")
    doc.save(path)
    doc.close()

    window = Win()
    assert window.minimumSize().width() == 700
    assert window.minimumSize().height() == 500
    assert window.isMinimized() is False
    assert window.search_text.accessibleName() == "Search document"
    assert window.btn_start.accessibleName() == "Start or pause"
    assert window.status.accessibleName() == "Dictation status"
    assert window.chunk.accessibleName() == "Current dictation chunk"
    assert window.bar.accessibleName() == "Writing progress"
    assert window.status.font().pointSize() == 20
    assert window.chunk.font().pointSize() == 16
    assert window.bar.maximumHeight() == 10
    assert window.bookmark_list.isHidden()
    assert window.thumbnail_list.accessibleName() == "Page thumbnails"
    assert not window.windowIcon().isNull()
    assert not window.back_button.isEnabled()
    assert not window.forward_button.isEnabled()
    window.doc = fitz.open(path)
    window.pages = 2
    window.page_spin.setRange(1, 2)
    window.populate_thumbnails()
    assert window.thumbnail_list.count() == 2
    window.open_thumbnail(window.thumbnail_list.item(1))
    assert window.page_spin.value() == 2
    window.page_spin.setValue(1)
    assert window.back_button.isEnabled()
    window.go_back()
    assert window.page_spin.value() == 2
    assert window.forward_button.isEnabled()
    window.go_forward()
    assert window.page_spin.value() == 1
    window.search_text.setText("target")
    window.search_document()

    assert window.search_results.count() == 1
    assert window.page_spin.value() == 2

    window.toggle_bookmark()
    assert window.bookmarks == [2]
    assert window.bookmark_list.count() == 1
    assert not window.bookmark_list.isHidden()
    window.page_spin.setValue(1)
    window.toggle_bookmark()
    assert window.bookmarks == [1, 2]
    window.close()
