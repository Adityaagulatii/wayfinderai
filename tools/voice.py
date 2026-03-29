"""
tools/voice.py — Shared voice layer for WayfinderAI
-----------------------------------------------------
  speak(text, block)  — TTS via pyttsx3 (Windows SAPI5)
  listen(prompt)      — STT via SpeechRecognition (falls back to keyboard)
  beep(kind)          — Audio tone via pygame (non-blocking)
"""
import sys
import threading
import queue

# ── TTS — one engine per call (most reliable on Windows) ──────────────────
try:
    import pyttsx3 as _pyttsx3
    _pyttsx3.init()   # quick check it works
    _TTS_OK = True
except Exception as e:
    print(f"[voice] TTS unavailable: {e}", file=sys.stderr)
    _TTS_OK = False

_tts_lock = threading.Lock()


def _speak_blocking(text: str) -> None:
    """Runs in its own thread so pyttsx3 always owns the thread it init'd in."""
    with _tts_lock:
        try:
            engine = _pyttsx3.init()
            engine.setProperty("rate", 155)
            engine.setProperty("volume", 1.0)
            engine.say(text)
            engine.runAndWait()
            engine.stop()
        except Exception as e:
            print(f"[voice] TTS error: {e}", file=sys.stderr)


def speak(text: str, block: bool = True) -> None:
    """
    Speak text aloud.
    block=True  — waits until speech finishes (use for instructions)
    block=False — fires in background (use inside camera loops)
    """
    if not _TTS_OK or not text:
        return
    t = threading.Thread(target=_speak_blocking, args=(text,), daemon=True)
    t.start()
    if block:
        t.join()


# ── STT ───────────────────────────────────────────────────────────────────
try:
    import speech_recognition as _sr
    _STT_OK = True
except ImportError:
    _STT_OK = False


def listen(prompt: str = "") -> str:
    """
    Speak the prompt once, then listen for up to 60 seconds total.
    - If nothing heard after 30s → asks "Are you there?"
    - If still nothing after another 30s → gives up gracefully
    No typing fallback — fully voice driven.
    """
    if not _STT_OK:
        speak("Sorry, microphone is not available on this device.")
        return ""

    try:
        mic = _sr.Microphone()
    except OSError:
        speak("Sorry, I could not access the microphone.")
        return ""

    r = _sr.Recognizer()

    # Speak the prompt only once before listening
    if prompt:
        speak(prompt, block=True)

    for round_ in range(2):   # round 0: first 30s, round 1: after "are you there?"
        print("  [listening...]")
        try:
            with mic as source:
                r.adjust_for_ambient_noise(source, duration=0.3)
                audio = r.listen(source, timeout=30, phrase_time_limit=15)
            result = r.recognize_google(audio).lower().strip()
            print(f"  [heard]: {result}")
            return result
        except _sr.WaitTimeoutError:
            if round_ == 0:
                speak("Are you there? I'm still listening.")
            else:
                speak("I didn't hear anything. Let me ask you again.")
        except _sr.UnknownValueError:
            if round_ == 0:
                speak("Sorry, I didn't catch that. Could you say that again?")
            else:
                speak("I'm having trouble hearing you clearly. Let me ask again.")
        except Exception as e:
            print(f"  [STT error: {e}]")
            speak("Something went wrong with the microphone. Let me try again.")

    return ""


# ── Audio cues — generated sine tones ────────────────────────────────────
try:
    import pygame as _pygame
    import numpy as _np
    _pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=512)
    _BEEP_OK = True
except Exception as e:
    print(f"[voice] Audio cues unavailable: {e}", file=sys.stderr)
    _BEEP_OK = False

_CUE_FREQS: dict[str, int] = {
    "detect":   880,
    "found":    1046,
    "arrive":   660,
    "left":     400,
    "right":    520,
    "straight": 300,
    "error":    200,
    "start":    740,
}


def narrate(context: str, instruction: str) -> str:
    """
    LLM-powered spoken narration for visually impaired users.
    Always returns 1-2 short sentences using spatial, accessible language.
    Uses ollama llama3.2 locally — no API key needed.
    """
    try:
        import ollama
        response = ollama.chat(
            model="llama3.2:latest",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a voice navigation assistant helping a visually impaired shopper "
                        "in a Kroger grocery store. "
                        "Use clear, spatial language: left, right, straight ahead, top shelf, "
                        "bottom shelf, reach up, reach down, turn around, a few steps ahead. "
                        "Speak in 1-2 SHORT sentences only. "
                        "No markdown, no lists, no bullet points. "
                        "Be calm, clear, and precise — the person cannot see anything."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Situation: {context}\nSay: {instruction}",
                },
            ],
        )
        return response["message"]["content"].strip()
    except Exception:
        return instruction


def beep(kind: str = "detect", duration_ms: int = 220) -> None:
    """Play a short tone immediately (non-blocking)."""
    if not _BEEP_OK:
        return
    try:
        freq = _CUE_FREQS.get(kind, 440)
        n    = int(44100 * duration_ms / 1000)
        t    = _np.linspace(0, duration_ms / 1000, n, endpoint=False)
        fade = _np.clip(_np.minimum(t / 0.01, (duration_ms / 1000 - t) / 0.01), 0, 1)
        wave = (_np.sin(2 * _np.pi * freq * t) * fade * 32767).astype(_np.int16)
        _pygame.sndarray.make_sound(wave).play()
    except Exception:
        pass
