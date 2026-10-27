"""Qt-free dictation state machine. Drive it by calling tick() every ~100 ms."""
import time
from enum import Enum
from dataclasses import dataclass
from .chunker import ImageItem, WordRules, timing_char_count, writing_time
from .textprep import prepare_speech, looks_like_code


class State(Enum):
    IDLE = "IDLE"; READY = "READY"; SPEAKING = "SPEAKING"; WRITING = "WRITING"
    PAUSED = "PAUSED"; IMAGE_PAUSED = "IMAGE_PAUSED"; FINISHED = "FINISHED"; ERROR = "ERROR"


@dataclass
class Settings:
    seconds_per_char: float = 0.75
    extra_pause: float = 0.0
    writing_profile: str = "prose"  # "prose" | "code" | "equations" | "custom"
    pause_at_images: bool = True
    speak_punctuation: bool = False
    speak_symbols: bool = False
    speech_profile: str = "automatic"  # "prose" | "code" | "automatic"
    normalize: bool = True
    target: float = 3.0
    short_weight: float = 0.5
    long_weight: float = 1.0
    short_max: int = 3
    min_img_w: int = 100
    min_img_h: int = 100
    voice_id: str = ""
    rate: int = 150
    volume: float = 1.0
    ocr_mode: str = "auto"      # "auto" | "off"
    ocr_language: str = "eng"
    use_ocr_cache: bool = True
    auto_update: bool = False
    enable_plugins: bool = False
    license_accepted: bool = False

    def word_rules(self):
        return WordRules(self.short_weight, self.long_weight, self.short_max, self.target)


class Controller:
    def __init__(self, items, speech, settings=None, clock=time.monotonic, on_change=None):
        self.items, self.speech = items, speech
        self.s = settings or Settings()
        self.clock, self.on_change = clock, on_change or (lambda: None)
        self.index, self.state = 0, State.READY if items else State.IDLE
        self.remaining, self.deadline, self._paused_from = 0.0, 0.0, None

    @property
    def item(self): return self.items[self.index] if self.index < len(self.items) else None

    def time_left(self):
        if self.state == State.WRITING: return max(0.0, self.deadline - self.clock())
        return self.remaining

    def _set(self, st): self.state = st; self.on_change()

    def _enter(self):
        it = self.item
        if it is None: return self._set(State.FINISHED)
        if isinstance(it, ImageItem):
            if self.s.pause_at_images: return self._set(State.IMAGE_PAUSED)
            self.index += 1; return self._enter()
        chars = timing_char_count(it.text, self.s.writing_profile)
        self.remaining = writing_time(chars, self.s.seconds_per_char, self.s.extra_pause)
        speak_symbols = self.s.speak_symbols or self.s.speech_profile == "code"
        if self.s.speech_profile == "automatic" and looks_like_code(it.text):
            speak_symbols = True
        self.speech.speak(prepare_speech(it.text, self.s.speak_punctuation, self.s.normalize, speak_symbols))
        self._set(State.SPEAKING)

    def tick(self):
        if self.state == State.SPEAKING and not self.speech.is_speaking():
            if self.speech.last_error:
                self._set(State.ERROR)
            else:
                self.deadline = self.clock() + self.remaining; self._set(State.WRITING)  # timer starts AFTER speech
        elif self.state == State.WRITING and self.clock() >= self.deadline:
            self.index += 1; self.remaining = 0.0; self._enter()

    def start(self):
        if self.state in (State.READY, State.PAUSED): self._enter()

    def toggle(self):
        st = self.state
        if st == State.IMAGE_PAUSED: self.index += 1; self._enter()
        elif st == State.SPEAKING: self.speech.stop(); self._paused_from = st; self._set(State.PAUSED)
        elif st == State.WRITING:
            self.remaining = max(0.0, self.deadline - self.clock())
            self._paused_from = st; self._set(State.PAUSED)
        elif st == State.PAUSED:
            if self._paused_from == State.WRITING:
                self.deadline = self.clock() + self.remaining; self._set(State.WRITING)
            else: self._enter()
            self._paused_from = None
        elif st == State.READY: self.start()
        elif st == State.ERROR: self._enter()  # retry on error

    def repeat(self):
        if isinstance(self.item, ImageItem) or self.item is None: return
        self.speech.stop(); self.speech.last_error = None; self._enter()   # re-speak, then full timer again

    def _move(self, d):
        n = self.index + d
        if 0 <= n < len(self.items):
            self.speech.stop(); self.index = n; self.remaining = 0.0
            self._paused_from = None; self._set(State.PAUSED)  # waits for user to resume

    def next(self): self._move(1)
    def prev(self): self._move(-1)

    def stop(self):
        self.speech.stop(); self._set(State.READY)
