from enum import StrEnum
import os

from dotenv import load_dotenv


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
