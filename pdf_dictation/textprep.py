"""Speech-friendly text preparation (optional; never changes what counts for timing)."""
import re

NAMES = {",": "comma", ".": "period", ";": "semicolon", ":": "colon", "?": "question mark", "!": "exclamation mark"}
SYMBOL_NAMES = {
    **NAMES,
    "(": "left parenthesis", ")": "right parenthesis",
    "[": "left bracket", "]": "right bracket",
    "{": "left brace", "}": "right brace",
    "<": "less than", ">": "greater than",
    "+": "plus", "-": "minus", "*": "asterisk", "/": "slash",
    "=": "equals", "%": "percent", "&": "ampersand", "|": "vertical bar",
    "^": "caret", "~": "tilde", "_": "underscore", "#": "hash",
    "@": "at", "$": "dollar", "\\": "backslash", "`": "backtick",
    "'": "single quote", '"': "double quote",
}


def looks_like_code(text):
    symbols = len(re.findall(r"[{}[\]();=<>]|//|&&|\|\||:\s*$", text, re.MULTILINE))
    identifiers = len(re.findall(r"\b[A-Za-z_]\w*\b", text))
    return symbols >= 2 or (symbols >= 1 and identifiers >= 3)


def prepare_speech(text, speak_punctuation=False, normalize=True, speak_symbols=False):
    if normalize:
        text = re.sub(r"\bFig\.", "Figure", text)
        text = re.sub(r"\be\.g\.", "for example", text)
        text = re.sub(r"\bi\.e\.", "that is", text)
        text = re.sub(r"(?<=\d)\.(?=\d)", " point ", text)   # 3.2 -> 3 point 2
    if speak_punctuation:
        text = re.sub(r"([,.;:?!])", lambda m: f", {NAMES[m.group(1)]},", text)
    if speak_symbols:
        text = re.sub(r"([^\w\s])", lambda m: f", {SYMBOL_NAMES.get(m.group(1), m.group(1))},", text)
        text = re.sub(r"\s+", " ", text).strip()
        text = re.sub(r",\s*,", ",", text)
    return text
