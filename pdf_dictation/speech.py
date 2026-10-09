"""Offline TTS (pyttsx3).

Design rules (each one fixes a real failure mode):
* A FRESH engine is created for every utterance, inside that utterance's own worker thread.
  pyttsx3.init() caches one engine object per driver and keeps handing the same, possibly stale one back;
  a stale engine is the classic cause of "first chunk is spoken, the rest are silent".
* No shared lock: stop() must never block the GUI thread while speech is playing.
* Speech that returns suspiciously fast (nothing was really spoken) is retried once, then reported through
  `last_error` so the controller can show an error instead of silently starting the writing timer.
"""
import logging
import threading
import time

try:
    import pythoncom          # Windows only (installed with pyttsx3); SAPI5 needs COM initialised per thread
except ImportError:
    pythoncom = None

log = logging.getLogger("pdf_dictation")
MIN_SECONDS_PER_CHAR = 0.02   # faster than any real voice; finishing quicker than this means nothing was spoken


def _new_engine():
    import pyttsx3
    try:
        from pyttsx3.engine import Engine
        return Engine(None)    # bypasses pyttsx3.init()'s cache -> always a clean engine
    except Exception:
        return pyttsx3.init()


class SpeechEngine:
    def __init__(self, rate=150, volume=1.0, voice_id=None):
        self.rate, self.volume, self.voice_id = rate, volume, voice_id
        self._speaking, self._engine, self._gen = False, None, 0
        self.last_error = None

    def voices(self, extra=()):
        try:
            voices = [(v.id, v.name) for v in _new_engine().getProperty("voices")]
            existing = {voice_id for voice_id, _ in voices}
            voices.extend((profile.voice_id, profile.name) for profile in extra if profile.voice_id not in existing)
            return voices
        except Exception as ex:
            log.error("voice list failed: %s", ex); return []

    def diagnostics(self):
        try:
            voices = self.voices()
            selected = next((name for voice_id, name in voices if voice_id == self.voice_id), None)
            return {
                "backend": "pyttsx3",
                "voice_count": len(voices),
                "selected_voice": selected,
                "voice_available": not self.voice_id or selected is not None,
                "error": None,
            }
        except Exception as ex:
            return {
                "backend": "pyttsx3",
                "voice_count": 0,
                "selected_voice": None,
                "voice_available": False,
                "error": f"{type(ex).__name__}: {ex}",
            }

    def speak(self, text):
        self.stop()
        self._gen += 1; gen = self._gen
        self.last_error = None
        self._speaking = True          # set before the thread starts: no race with the controller's tick()
        threading.Thread(target=self._run, args=(text, gen), daemon=True).start()

    def _on_engine_error(self, name, exception):
        self._engine_error = f"{name}: {exception}"

    def _run(self, text, gen):
        try:
            if pythoncom: pythoncom.CoInitialize()
            need = len(text) * MIN_SECONDS_PER_CHAR
            for attempt in (1, 2):
                e = _new_engine(); self._engine = e
                self._engine_error = None
                try:
                    e.connect("error", self._on_engine_error)
                except Exception:
                    log.debug("TTS engine does not expose error callbacks", exc_info=True)
                e.setProperty("rate", self.rate); e.setProperty("volume", self.volume)
                if self.voice_id: e.setProperty("voice", self.voice_id)
                t0 = time.monotonic()
                e.say(text); e.runAndWait()
                took = time.monotonic() - t0
                if gen != self._gen: return            # stopped on purpose, not a failure
                if not self._engine_error and took >= need: return  # spoke normally
                if self._engine_error:
                    reason = f" ({self._engine_error})"
                    log.warning("TTS attempt %d reported an engine error%s; retrying", attempt, reason)
                else:
                    reason = ""
                    log.warning("TTS attempt %d finished in %.2fs (expected >= %.2fs); retrying", attempt, took, need)
                self._engine = None; del e
            if gen == self._gen:
                detail = f" ({self._engine_error})" if self._engine_error else ""
                self.last_error = f"Speech failed after 2 attempts{detail}."
        except Exception as ex:
            log.error("TTS error: %s", ex)
            if gen == self._gen: self.last_error = f"{type(ex).__name__}: {ex}"
        finally:
            if gen == self._gen: self._speaking = False   # last_error is already set when this flips

    def stop(self):
        self._gen += 1; self._speaking = False
        e, self._engine = self._engine, None
        try:
            if e: e.stop()
        except Exception: pass

    def pause(self): self.stop()
    def resume(self): pass   # the controller re-speaks the chunk
    def is_speaking(self): return self._speaking
