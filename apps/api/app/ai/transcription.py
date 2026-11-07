"""Speech-to-text provider abstraction. Default: open-source Whisper (faster-whisper), run locally."""

from pathlib import Path
from typing import Protocol

from app.core.config import get_settings


class Transcriber(Protocol):
    name: str

    def transcribe(self, audio: Path) -> dict: ...


class TranscriptionUnavailable(Exception):
    pass


class LocalWhisper:
    """faster-whisper on CPU, int8. The model downloads once (cached in HF_HOME)."""

    _model = None
    _model_name: str | None = None

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or get_settings().whisper_model
        self.name = f"whisper-{self.model_name} (local)"

    def _load(self):
        if LocalWhisper._model is None or LocalWhisper._model_name != self.model_name:
            try:
                from faster_whisper import WhisperModel
            except ImportError as e:
                raise TranscriptionUnavailable("faster-whisper is not installed") from e
            LocalWhisper._model = WhisperModel(self.model_name, device="cpu", compute_type="int8")
            LocalWhisper._model_name = self.model_name
        return LocalWhisper._model

    def transcribe(self, audio: Path) -> dict:
        model = self._load()
        segments, info = model.transcribe(str(audio), word_timestamps=True, vad_filter=True)
        out = []
        for seg in segments:
            out.append({
                "start": round(seg.start, 2),
                "end": round(seg.end, 2),
                "text": seg.text.strip(),
                "words": [
                    {"start": round(w.start, 2), "end": round(w.end, 2), "word": w.word.strip()}
                    for w in (seg.words or [])
                ],
            })
        return {"language": info.language, "duration": info.duration, "segments": out, "engine": self.name}


def get_transcriber() -> Transcriber:
    if not get_settings().whisper_enabled:
        raise TranscriptionUnavailable("Whisper is disabled (WHISPER_ENABLED=false)")
    return LocalWhisper()
