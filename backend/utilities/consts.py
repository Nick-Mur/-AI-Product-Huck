from enum import StrEnum


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
