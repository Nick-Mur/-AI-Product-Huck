import whisper
import warnings
from utilities.consts import (
    WhisperModelsENUM,
    SupportedLanguagesCodesEnum,
    SupportedExtensionsEnum,
    GeminiModelsEnum,
    GOOGLE_API_KEY,
)
from google import genai


class AudioToText:
    def __init__(self,
                 audio_file_content=None,
                 audio_file_path=None,
                 language=SupportedLanguagesCodesEnum.RU,
                 whisper_model=WhisperModelsENUM.TINY,
                 gemini_model=GeminiModelsEnum.gemini_2_5_flash):

        self.language = language

        self.whisper_model = whisper_model

        self.audio_file_path = audio_file_path

        # Store content early so validation can distinguish path vs content flows
        self.audio_content = audio_file_content

        self.gemini_model = gemini_model

        self._validate_init()

        if self.audio_content is None and self.audio_file_path:
            # Only load bytes if explicitly needed later; whisper prefers a file path
            self.audio_content = None

        self.transcribed_text = self.client = self.whisper = None

    def transcribe_file(self):
        """Transcribe audio and store plain text using Whisper.
        Prefers file path input for stability/performance.
        """

        if self.whisper is None:
            self.whisper = whisper.load_model(str(self.whisper_model))

        source = self.audio_file_path if self.audio_file_path else self.audio_content
        if source is None:
            raise ValueError("No audio provided for transcription")

        # Avoid FP16 warning on CPU and force FP32
        warnings.filterwarnings("ignore", message=r".*FP16 is not supported on CPU.*")
        result = self.whisper.transcribe(source, language=str(self.language), fp16=False)
        text = result.get('text') if isinstance(result, dict) else None
        self.transcribed_text = text if isinstance(text, str) else str(result)
        return self.transcribed_text

    def restore_transcribed_text_with_gemini(self):
        """Use Gemini to enhance punctuation, casing, and spacing of the transcribed text."""

        if self.client is None:
            if not GOOGLE_API_KEY:
                raise ValueError("GOOGLE_API_KEY is not set in environment")
            self.client = genai.Client(api_key=GOOGLE_API_KEY)

        if not self.transcribed_text:
            raise ValueError("Transcribed text is empty. Run transcribe_file() first.")

        instruction = (
            "Ты помощник по восстановлению пунктуации и регистра в тексте, полученном из распознавания речи. "
            "Поправь пунктуацию, регистр, явные опечатки, разбей на абзацы. Ничего не добавляй и не сокращай. "
            f"Сохрани исходный язык: {self.language}. Верни только исправленный текст."
        )

        response = self.client.models.generate_content(
            model=str(self.gemini_model),
            contents=[
                {"role": "user", "parts": [
                    {"text": instruction},
                ]},
                {"role": "user", "parts": [
                    {"text": self.transcribed_text},
                ]},
            ],
        )

        self.transcribed_text = (response.text or "").strip()
        return self.transcribed_text


    def _get_audio_file_content(self):
        try:
            with open(self.audio_file_path, 'rb') as f:
                return f.read()
        except Exception as e:
            raise ValueError(f"Error reading audio file: {e}")

    def _validate_init(self):
        """Validate initialization parameters.
         Проверка параметров инициализации.
         """
        try:
            self.language = SupportedLanguagesCodesEnum(self.language)
        except ValueError as exc:
            supported_langs = ", ".join(map(str, SupportedLanguagesCodesEnum))
            raise ValueError(
                (
                    f"Language '{self.language}' is not supported. "
                    "Supported languages are: "
                    f"{supported_langs}"
                )
            ) from exc


        try:
            self.whisper_model = WhisperModelsENUM(self.whisper_model)
        except ValueError as exc:
            supported_models = ", ".join(map(str, WhisperModelsENUM))
            raise ValueError(
                (
                    f"Whisper model '{self.whisper_model}' is not supported. "
                    "Supported models are: "
                    f"{supported_models}"
                )
            ) from exc


        try:
            self.gemini_model = GeminiModelsEnum(self.gemini_model)
        except ValueError as exc:
            supported_models = ", ".join(map(str, GeminiModelsEnum))
            raise ValueError(
                (
                    f"Gemini model '{self.whisper_model}' is not supported. "
                    "Supported models are: "
                    f"{supported_models}"
                )
            ) from exc

        # Ensure either content or path is provided
        if self.audio_content is None and not self.audio_file_path:
            raise ValueError(
                "Provide either 'audio_file_content' or a valid 'audio_file_path'."
            )

        # If path provided, validate extension
        if self.audio_file_path and not self.audio_file_path.endswith(tuple(SupportedExtensionsEnum)):
            supported_exts = ", ".join(map(str, SupportedExtensionsEnum))
            raise ValueError(
                "File extension is not supported. Supported extensions are: "
                f"{supported_exts}"
            )
