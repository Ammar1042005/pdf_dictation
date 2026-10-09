import pytest
from pdf_dictation.chunker import *
from pdf_dictation.controller import Controller, State, Settings
from pdf_dictation.extractor import (reading_order, Entry, keep_image, load_items, table_entries,
                                     classify_image, vector_diagram_regions, search_document)
from pdf_dictation import sessions


@pytest.mark.parametrize("w,e", [("a", .5), ("an", .5), ("the", .5), ("cell", 1), ("mitochondria", 1),
                                 ("cell,", 1), ("(cell)", 1), ("book.", 1), ("DNA", .5), ("2025", 1)])
def test_weights(w, e): assert word_weight(w) == e


def test_timing(): assert writing_time(char_count("The cell is large."), 0.75) == 10.5


def test_timing_profiles():
    from pdf_dictation.chunker import timing_char_count
    assert timing_char_count("x += 1;", "prose") == 2
    assert timing_char_count("x += 1;", "code") == 5
    assert timing_char_count("x + y", "equations") == 3


def test_diagnostics_report_excludes_document_content():
    from pdf_dictation.diagnostics import report
    data = report(Settings())
    serialized = str(data)
    assert data["application"] == "PDFDictation"
    assert "document" not in serialized.lower()
    assert "chunk" not in serialized.lower()


def test_search_document_returns_page_matches(tmp_path):
    fitz = pytest.importorskip("pymupdf")
    path = tmp_path / "search.pdf"
    doc = fitz.open()
    doc.new_page().insert_text((50, 50), "alpha beta")
    doc.new_page().insert_text((50, 50), "beta gamma")
    doc.save(path)
    doc.close()
    doc = fitz.open(path)
    matches = search_document(doc, "beta")
    assert [page for page, _ in matches] == [1, 2]
    assert search_document(doc, "missing") == []
    doc.close()


def test_example_chunks():
    c = TextChunker().create_chunks("The cell membrane controls the movement of substances")
    assert c[0].text == "The cell membrane controls" and c[0].word_units == 3.5 and c[0].character_count == 23
    assert writing_time(c[0].character_count) == 17.25
    assert TextChunker().create_chunks("I am studying mitochondria")[0].word_units == 3.0


def test_words_never_split_and_paragraphs_separate():
    c = TextChunker().create_chunks("electroencephalography\n\nNext para here")
    assert c[0].text == "electroencephalography" and len(c) == 2


def test_sentence_boundary():
    c = TextChunker().create_chunks("The cell is large. Another one here today")
    assert c[0].text == "The cell is large."


def test_sentence_boundary_ignores_abbreviations_and_decimals():
    c = TextChunker().create_chunks("Use e.g. 3.2 units before the next sentence. Continue here.")
    assert all(chunk.text not in ("Use e.g.", "Use e.g. 3.2") for chunk in c)


def test_code_tokens_are_not_split_at_internal_symbols():
    chunks = TextChunker().create_chunks("Call object.method_name and package::Type next")
    assert any("object.method_name" in chunk.text for chunk in chunks)
    assert any("package::Type" in chunk.text for chunk in chunks)


def test_formula_tokens_are_not_split():
    chunks = TextChunker().create_chunks(r"Use \frac a b and x^2 plus √n in the equation")
    assert any(r"\frac" in chunk.text for chunk in chunks)
    assert any("x^2" in chunk.text for chunk in chunks)
    assert any("√n" in chunk.text for chunk in chunks)


def test_list_markers_are_not_sentence_boundaries():
    chunks = TextChunker().create_chunks("1. First item 2. Second item 3. Final item")
    assert all(chunk.text not in ("1.", "2.", "3.") for chunk in chunks)


def test_code_semicolons_are_not_sentence_boundaries():
    chunks = TextChunker().create_chunks("if (x) { return x; } else { return 0; }")
    assert not any(chunk.text.endswith("x;") or chunk.text.endswith("0;") for chunk in chunks)


def test_code_chunks_never_cross_source_lines():
    chunks = TextChunker().create_chunks(
        "if (value >= 2) {\n    return value;\n}",
        preserve_lines=True,
    )
    assert [chunk.text for chunk in chunks] == ["if (value >= 2) {", "return value;", "}"]


class FakeSpeech:
    def __init__(s): s.on = False; s.said = []; s.last_error = None
    def speak(s, t): s.on = True; s.said.append(t); s.last_error = None
    def stop(s): s.on = False
    def is_speaking(s): return s.on


def make(items):
    t = [0.0]; sp = FakeSpeech()
    return Controller(items, sp, Settings(), clock=lambda: t[0]), sp, t


def test_timer_starts_after_speech_and_image_pause():
    ch = TextChunker().create_chunks("The cell membrane controls")  # 23 chars -> 17.25 s
    c, sp, t = make(ch + [ImageItem(1, (0, 0, 200, 200))] + TextChunker().create_chunks("Hello world today"))
    c.start(); assert c.state == State.SPEAKING
    t[0] = 100; c.tick(); assert c.state == State.SPEAKING
    sp.on = False; c.tick(); assert c.state == State.WRITING
    t[0] = 100 + 17; c.tick(); assert c.state == State.WRITING
    t[0] = 100 + 17.3; c.tick(); assert c.state == State.IMAGE_PAUSED
    c.toggle(); assert c.state == State.SPEAKING and sp.said[-1] == "Hello world today"


def test_pause_freezes_and_repeat_restarts():
    c, sp, t = make(TextChunker().create_chunks("The cell membrane controls"))
    c.start(); sp.on = False; c.tick(); t[0] = 10; c.toggle()
    assert c.state == State.PAUSED; t[0] = 500; c.toggle()
    assert c.state == State.WRITING and abs(c.time_left() - 7.25) < 1e-9
    c.repeat(); assert c.state == State.SPEAKING and len(sp.said) == 2 and c.index == 0


def test_reading_order_two_columns():
    E = lambda r, n: Entry(r, "text", n)
    es = [E((0, 0, 600, 50), "title"), E((320, 60, 580, 100), "R1"), E((20, 60, 280, 100), "L1"),
          E((20, 110, 280, 150), "L2")]
    assert [e.payload for e in reading_order(es, 600)] == ["title", "L1", "L2", "R1"]
    assert not keep_image((0, 0, 20, 20), 100, 100)


def test_reading_order_asymmetric_columns():
    E = lambda r, n: Entry(r, "text", n)
    es = [
        E((300, 40, 800, 70), "L1"),
        E((300, 80, 800, 110), "L2"),
        E((820, 40, 980, 70), "R1"),
        E((820, 80, 980, 110), "R2"),
    ]
    assert [e.payload for e in reading_order(es, 1000)] == ["L1", "L2", "R1", "R2"]


def test_table_entries_are_row_major():
    class Table:
        bbox = (10, 20, 200, 100)

        def extract(self):
            return [["Name", "Value"], ["alpha", "1"], ["beta", "2"]]

    class Page:
        def find_tables(self):
            return type("Tables", (), {"tables": [Table()]})()

    entries = table_entries(Page(), 1)
    assert len(entries) == 1
    assert entries[0].rect == (10, 20, 200, 100)
    assert entries[0].payload == "Name | Value\nalpha | 1\nbeta | 2"


def test_sessions(tmp_path):
    a, b = tmp_path / "a.pdf", tmp_path / "b.pdf"; a.write_bytes(b"A"); b.write_bytes(b"B")
    sessions.save(str(a), 43, {}, tmp_path)
    assert sessions.load(str(a), tmp_path)["chunk_index"] == 43 and sessions.load(str(b), tmp_path) is None


def test_textprep():
    from pdf_dictation.textprep import prepare_speech as p, looks_like_code
    assert p("Figure 3.2 shows it.") == "Figure 3 point 2 shows it."
    assert p("Fig. 1") == "Figure 1"
    assert p("The cell, large.", speak_punctuation=True) == "The cell, comma, large, period,"
    assert p("A, b.", speak_punctuation=False) == "A, b."
    assert p("x >= 2", speak_symbols=True) == "x , greater than, equals, 2"
    assert looks_like_code("if (x >= 2) { return x; }")
    assert not looks_like_code("The cell membrane controls movement.")


def test_automatic_code_speech_profile():
    ch = TextChunker().create_chunks("if (x >= 2) { return x; }")
    settings = Settings()
    assert settings.speech_profile == "automatic"
    speech = FakeSpeech()
    controller = Controller(ch, speech, settings)
    controller.start()
    assert "greater than" in speech.said[-1]


def test_settings_roundtrip(tmp_path):
    from pdf_dictation import settings as cfg
    s = cfg.load(tmp_path / "x.json"); assert s.seconds_per_char == 0.75      # missing file -> defaults
    s.seconds_per_char, s.rate = 1.25, 170; cfg.save(s, tmp_path / "x.json")
    r = cfg.load(tmp_path / "x.json"); assert (r.seconds_per_char, r.rate) == (1.25, 170)
    assert r.word_rules().target == 3.0


def test_ocr_helpers():
    from pdf_dictation.extractor import needs_ocr, is_page_scan
    assert needs_ocr([]) and needs_ocr([((0, 0, 1, 1), "  p. 3 ")]) and not needs_ocr([((0, 0, 1, 1), "A real paragraph of text here.")])
    assert is_page_scan((0, 0, 600, 790), (0, 0, 612, 792)) and not is_page_scan((50, 50, 300, 300), (0, 0, 612, 792))


def test_ocr_settings_roundtrip(tmp_path):
    from pdf_dictation import settings as cfg
    s = cfg.load(tmp_path / "o.json"); assert (s.ocr_mode, s.ocr_language) == ("auto", "eng")
    s.ocr_language = "hin"; cfg.save(s, tmp_path / "o.json"); assert cfg.load(tmp_path / "o.json").ocr_language == "hin"


def test_ocr_cache(tmp_path):
    from pdf_dictation import sessions
    a, b = tmp_path / "a.pdf", tmp_path / "b.pdf"; a.write_bytes(b"A"); b.write_bytes(b"B")
    blocks = [((0, 0, 100, 50), "test text")]
    # Save and load cache
    sessions.save_ocr_cache(str(a), 1, blocks, "eng", tmp_path)
    loaded = sessions.load_ocr_cache(str(a), 1, "eng", tmp_path)
    assert loaded == blocks
    # Different PDF should not get cache
    assert sessions.load_ocr_cache(str(b), 1, "eng", tmp_path) is None
    # Different page should not get cache
    assert sessions.load_ocr_cache(str(a), 2, "eng", tmp_path) is None
    # Different language should not get cache
    assert sessions.load_ocr_cache(str(a), 1, "fra", tmp_path) is None


def test_ocr_cache_preserves_word_boxes(tmp_path):
    from pdf_dictation import sessions
    pdf = tmp_path / "words.pdf"
    pdf.write_bytes(b"PDF")
    blocks = [((0, 0, 100, 50), "hello world", [((0, 0, 40, 20), "hello")])]
    sessions.save_ocr_cache(str(pdf), 1, blocks, "eng", tmp_path)
    assert sessions.load_ocr_cache(str(pdf), 1, "eng", tmp_path) == blocks


def test_pdf_fixture_layouts(tmp_path):
    import base64
    fitz = pytest.importorskip("pymupdf")
    path = tmp_path / "layouts.pdf"
    doc = fitz.open()
    page = doc.new_page(width=600, height=800)
    page.insert_textbox((50, 40, 550, 80), "Single column heading and paragraph.")
    page.insert_textbox((300, 120, 560, 170), "Left column crosses the page midpoint.")
    page.insert_textbox((40, 120, 260, 170), "First column starts on the left.")
    page.insert_textbox((40, 180, 260, 230), "First column continues below.")
    page.insert_textbox((300, 180, 560, 230), "Second column follows the first.")
    page.insert_textbox((60, 300, 540, 340), "Code: if (x >= 2) { return x; }")
    page = doc.new_page(width=600, height=800)
    page.insert_textbox((50, 40, 550, 80), "A page with text and a figure.")
    image = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
        "YAAAAAYAAjCB0C8AAAAASUVORK5CYII="
    )
    page.insert_image((100, 120, 300, 300), stream=image)
    page.insert_textbox((50, 340, 550, 390), "Text after the figure remains extractable.")
    doc.save(path)
    doc.close()

    loaded = load_items(str(path), min_w=100, min_h=100, ocr_mode="off")
    texts = [item.text for item in loaded.items if isinstance(item, Chunk)]
    assert loaded.pages == 2
    assert any("Single column heading" in text for text in texts)
    assert any("Code:" in text for text in texts)
    assert any(isinstance(item, ImageItem) for item in loaded.items)
    assert loaded.warnings == []


def test_extracted_code_chunks_preserve_lines(tmp_path):
    fitz = pytest.importorskip("pymupdf")
    path = tmp_path / "multiline-code.pdf"
    doc = fitz.open()
    page = doc.new_page(width=600, height=400)
    page.insert_textbox(
        (50, 50, 550, 180),
        "if (value >= 2) {\n    return value;\n}",
        fontsize=12,
    )
    doc.save(path)
    doc.close()

    loaded = load_items(str(path), ocr_mode="off")
    texts = [item.text for item in loaded.items if isinstance(item, Chunk)]
    assert texts == ["if (value >= 2) {", "return value;", "}"]


def test_pdf_fixture_sidebar_and_caption(tmp_path):
    fitz = pytest.importorskip("pymupdf")
    path = tmp_path / "sidebar.pdf"
    doc = fitz.open()
    page = doc.new_page(width=700, height=800)
    page.insert_textbox((50, 50, 430, 100), "Main body paragraph comes first.")
    page.insert_textbox((500, 50, 670, 180), "Sidebar note: remember this definition.")
    page.insert_textbox((100, 280, 400, 320), "Figure 1. Example caption.")
    doc.save(path)
    doc.close()

    loaded = load_items(str(path), ocr_mode="off")
    texts = [item.text for item in loaded.items if isinstance(item, Chunk)]
    assert any("Main body paragraph" in text for text in texts)
    assert any("Sidebar note" in text for text in texts)
    assert any("Example caption" in text for text in texts)


def test_image_classification_uses_caption_and_area():
    kind, caption = classify_image(
        (100, 150, 400, 400),
        [((100, 410, 400, 440), "Figure 2. Architecture overview.")],
        (0, 0, 600, 800),
    )
    assert kind == "figure"
    assert caption.startswith("Figure 2")
    kind, caption = classify_image((20, 20, 60, 60), [], (0, 0, 600, 800))
    assert kind == "image"
    assert caption == ""


def test_vector_diagram_regions():
    class Page:
        def get_drawings(self):
            return [{"rect": (100, 100, 180, 180)}, {"rect": (200, 120, 280, 200)},
                    {"rect": (120, 220, 200, 300)}, {"rect": (220, 240, 300, 320)}]
    regions = vector_diagram_regions(Page())
    assert regions == [(100, 100, 300, 320)]


def test_pdf_fixture_reports_unavailable_ocr(tmp_path, monkeypatch):
    fitz = pytest.importorskip("pymupdf")
    from pdf_dictation import extractor

    path = tmp_path / "mixed.pdf"
    doc = fitz.open()
    doc.new_page(width=400, height=400)
    page = doc.new_page(width=400, height=400)
    page.insert_text((50, 100), "This page has a text layer.")
    doc.save(path)
    doc.close()
    monkeypatch.setattr(extractor.ocr, "available", lambda *_args: False)
    monkeypatch.setattr(
        extractor.ocr,
        "availability_error",
        lambda *_args: "Tesseract is not installed or its tessdata directory could not be found.",
    )

    loaded = load_items(str(path), ocr_mode="auto")
    assert loaded.skipped_pages == [1]
    assert loaded.warnings == [
        "Page 1: text layer is missing. Tesseract is not installed or its tessdata directory could not be found."
    ]


def test_ocr_integration_pipeline_preserves_words_and_coordinates(tmp_path, monkeypatch):
    fitz = pytest.importorskip("pymupdf")
    from pdf_dictation import extractor

    path = tmp_path / "ocr-page.pdf"
    doc = fitz.open()
    doc.new_page(width=400, height=400)
    doc.save(path)
    doc.close()
    ocr_blocks = [(
        (50, 80, 250, 110),
        "Scanned text",
        [((50, 80, 120, 110), "Scanned"), ((125, 80, 250, 110), "text")],
    )]
    monkeypatch.setattr(extractor.ocr, "available", lambda *_args: True)
    monkeypatch.setattr(extractor.ocr, "ocr_blocks", lambda *_args: ocr_blocks)

    loaded = load_items(str(path), ocr_mode="auto", use_ocr_cache=False)
    chunks = [item for item in loaded.items if isinstance(item, Chunk)]
    assert loaded.ocr_pages == 1
    assert len(chunks) == 1
    assert chunks[0].text == "Scanned text"
    assert chunks[0].word_bboxes == ocr_blocks[0][2]


def test_ocr_language_validation(tmp_path, monkeypatch):
    from pdf_dictation import ocr

    tessdata = tmp_path / "tessdata"
    tessdata.mkdir()
    (tessdata / "eng.traineddata").write_bytes(b"eng")
    monkeypatch.setattr(ocr, "tessdata", lambda: str(tessdata))
    assert ocr.available("eng")
    assert not ocr.available("hin")
    assert ocr.availability_error("hin") == "OCR language data is missing: hin."


def test_speech_diagnostics(monkeypatch):
    from pdf_dictation.speech import SpeechEngine

    engine = SpeechEngine(voice_id="missing")
    monkeypatch.setattr(engine, "voices", lambda: [("voice-1", "Test voice")])
    result = engine.diagnostics()
    assert result["backend"] == "pyttsx3"
    assert result["voice_count"] == 1
    assert result["voice_available"] is False


def test_speech_engine_error_callback():
    from pdf_dictation.speech import SpeechEngine

    engine = SpeechEngine()
    engine._on_engine_error("sapi", RuntimeError("voice failed"))
    assert engine._engine_error == "sapi: voice failed"
