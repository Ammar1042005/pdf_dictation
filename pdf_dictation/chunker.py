"""Deterministic word-unit chunking and writing-time calculation."""
import re
from dataclasses import dataclass


@dataclass
class Chunk:
    text: str
    words: list
    word_units: float
    character_count: int
    page_number: int
    start_position: int = 0
    end_position: int = 0
    bbox: tuple = None   # block rectangle on the page (for highlighting)
    word_bboxes: list = None


@dataclass
class ImageItem:
    page_number: int
    bbox: tuple
    kind: str = "image"
    caption: str = ""


@dataclass
class WordRules:
    short_weight: float = 0.5
    long_weight: float = 1.0
    short_max: int = 3          # 1..short_max letters => short_weight
    target: float = 3.0
    sentence_min: float = 1.5   # close early at . ? ! ; : if at least this many units


def letters(tok): return sum(c.isalpha() for c in tok)
def char_count(text): return sum(c.isalnum() for c in text)  # no spaces/punctuation


def word_weight(tok, r=WordRules()):
    n = letters(tok) or char_count(tok)   # pure numbers: count digits
    if n == 0:
        return 0.0                         # lone punctuation
    return r.short_weight if n <= r.short_max else r.long_weight


def writing_time(chars, seconds_per_char=0.75, extra_pause=0.0):
    return chars * seconds_per_char + extra_pause


def timing_char_count(text, profile="prose"):
    if profile == "prose":
        return char_count(text)
    if profile in ("code", "equations"):
        return sum(not c.isspace() for c in text)
    return char_count(text)


def ends_sentence(token):
    """Recognize sentence punctuation without splitting common abbreviations."""
    stripped = token.rstrip("\"')]}").strip()
    if not stripped or stripped[-1] not in ".?!;:":
        return False
    if stripped[-1] == ".":
        if re.match(r"^(?:\(?\d+[.)]|\(?[A-Za-z][.)])$", stripped):
            return False
        if re.search(r"\b(?:e\.g|i\.e|etc|vs|fig|no|eq)\.$", stripped, re.IGNORECASE):
            return False
        if re.search(r"\d\.\d$", stripped):
            return False
    return True


def token_is_atomic(token):
    """Keep code-like tokens intact when they contain no whitespace."""
    return bool(re.search(
        r"[_\\/]|->|::|==|!=|<=|>=|&&|\|\||"
        r"[∑∫√≤≥≠≈∞]|\\(?:frac|sum|int|sqrt|alpha|beta|gamma)\b|"
        r"[A-Za-z]\^?\d+",
        token,
    ))


class TextChunker:
    def __init__(self, rules=None):
        self.rules = rules or WordRules()

    def create_chunks(self, text, page_number=1, preserve_lines=False):
        if preserve_lines:
            out = []
            for line in re.finditer(r"[^\r\n]+", text):
                if line.group().strip():
                    out.extend(self._para(line.group(), line.start(), page_number))
            return out
        out = []
        for para in re.finditer(r"\S(?:.|\n(?!\s*\n))*", text):
            out.extend(self._para(para.group(), para.start(), page_number))
        return out

    def _para(self, para, base, page):
        r, chunks, cur, units = self.rules, [], [], 0.0

        def flush():
            nonlocal cur, units
            if not cur:
                return
            ws = [m.group() for m in cur]
            c = Chunk(" ".join(ws), ws, units, sum(char_count(w) for w in ws), page,
                      base + cur[0].start(), base + cur[-1].end())
            if chunks and units < 1.0:   # avoid tiny trailing chunk: merge back
                p = chunks[-1]
                p.words += ws; p.text = " ".join(p.words); p.word_units += units
                p.character_count += c.character_count; p.end_position = c.end_position
            else:
                chunks.append(c)
            cur, units = [], 0.0

        for m in re.finditer(r"\S+", para):
            cur.append(m)
            units += word_weight(m.group(), r)
            if units >= r.target and not token_is_atomic(m.group()):
                flush()
            elif units >= r.sentence_min and ends_sentence(m.group()) and not (
                m.group().rstrip().endswith(";")
                and any(re.search(r"[{}()=<>]|->|::", word.group()) for word in cur)
            ):
                flush()
        flush()
        return chunks
