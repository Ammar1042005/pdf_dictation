import pytest

fitz = pytest.importorskip("pymupdf")

from pdf_dictation.chunker import Chunk, ImageItem
from pdf_dictation.extractor import load_items


def make_pdf(path, pages):
    doc = fitz.open()
    for page_builder in pages:
        page = doc.new_page(width=700, height=800)
        page_builder(page)
    doc.save(path)
    doc.close()


def text(page, rect, value, size=12):
    page.insert_textbox(rect, value, fontsize=size)


def test_sample_pdf_prose_columns_and_table(tmp_path):
    def build(page):
        text(page, (40, 40, 660, 80), "Sample document heading and introduction.")
        text(page, (40, 120, 300, 180), "Left column contains the first paragraph.")
        text(page, (390, 120, 660, 180), "Right column contains the second paragraph.")
        text(page, (40, 250, 660, 350), "Name | Value\nalpha | 1\nbeta | 2")
        page.draw_rect((40, 250, 300, 350))
        page.draw_line((170, 250), (170, 350))
        page.draw_line((40, 285), (300, 285))
        page.draw_line((40, 320), (300, 320))

    path = tmp_path / "prose-columns-table.pdf"
    make_pdf(path, [build])
    loaded = load_items(str(path), ocr_mode="off")
    texts = [item.text for item in loaded.items if isinstance(item, Chunk)]
    assert any("Left column" in value for value in texts)
    assert any("Right column" in value for value in texts)
    assert any("alpha" in value for value in texts)
    assert loaded.warnings == []


def test_sample_pdf_code_lines_and_figure(tmp_path):
    import base64

    def build(page):
        text(page, (40, 40, 660, 180), "for (item in items) {\n    process(item);\n}", size=11)
        image = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
            "YAAAAAYAAjCB0C8AAAAASUVORK5CYII="
        )
        page.insert_image((100, 260, 400, 560), stream=image)
        text(page, (100, 570, 400, 610), "Figure 1. Sample diagram.")

    path = tmp_path / "code-figure.pdf"
    make_pdf(path, [build])
    loaded = load_items(str(path), min_w=100, min_h=100, ocr_mode="off")
    texts = [item.text for item in loaded.items if isinstance(item, Chunk)]
    assert texts[:2] == ["for (item in items) {", "process(item);"]
    figures = [item for item in loaded.items if isinstance(item, ImageItem)]
    assert len(figures) == 1
    assert figures[0].kind == "figure"
    assert figures[0].caption.startswith("Figure 1")


def test_sample_pdf_scanned_page_uses_ocr_path(tmp_path, monkeypatch):
    from pdf_dictation import extractor

    path = tmp_path / "scanned.pdf"
    make_pdf(path, [lambda _page: None])
    monkeypatch.setattr(extractor.ocr, "available", lambda *_args: True)
    monkeypatch.setattr(
        extractor.ocr,
        "ocr_blocks",
        lambda *_args: [(
            (50, 50, 300, 90),
            "Sample OCR text",
            [((50, 50, 150, 90), "Sample"), ((155, 50, 300, 90), "OCR text")],
        )],
    )
    loaded = load_items(str(path), ocr_mode="auto", use_ocr_cache=False)
    assert loaded.ocr_pages == 1
    assert any(item.text == "Sample OCR text" for item in loaded.items if isinstance(item, Chunk))
