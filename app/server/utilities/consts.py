from enum import StrEnum
from dotenv import load_dotenv
import os


load_dotenv()


class WhisperModelsENUM(StrEnum):
    TINY = "tiny"
    BASE = "base"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"

class SupportedLanguagesCodesEnum(StrEnum):
    EN = "en"
    RU = "ru"

class SupportedExtensionsEnum(StrEnum):
    MP3 = ".mp3"
    MP4 = ".mp4"
    M4A = ".m4a"
    WAV = ".wav"
    WEBM = ".webm"
    OGG = ".ogg"


class GeminiModelsEnum(StrEnum):
    gemini_2_5_flash = "gemini-2.5-flash"


GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# If true, attach the source PDF to Gemini at review start
ANALIZE_PDF = (os.getenv("AnalizePDF", "false").strip().lower() in {"1", "true", "yes", "y"})

# If true, do NOT run Whisper transcription (helps on low‑RAM hosts)
DISABLE_TRANSCRIPTION = (os.getenv("DISABLE_TRANSCRIPTION", "false").strip().lower() in {"1", "true", "yes", "y"})

# Developer mode: when true, APIs may expose additional debugging data
# Supports either DevMode or DEV_MODE env variable names
DEV_MODE = (
    (os.getenv("DevMode") or os.getenv("DEV_MODE") or "false").strip().lower()
    in {"1", "true", "yes", "y"}
)

# Minimum number of positive/negative phrases Gemini should return per slide
# Supports both MinCount and MIN_COUNT env variable names; clamps to 0..5
def _read_min_count() -> int:
    raw = os.getenv("MinCount") or os.getenv("MIN_COUNT") or "1"
    try:
        v = int(str(raw).strip())
    except Exception:
        v = 1
    return max(0, min(5, v))

MIN_COUNT = _read_min_count()
