import whisper
from app.backend.utilities.consts import (
    WhisperModelsENUM,
    SupportedLanguagesCodesEnum,
    SupportedExtensionsEnum,
    GeminiModelsEnum,
    GOOGLE_API_KEY
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

        if self.audio_content is None:
            self.audio_content = self._get_audio_file_content()

        self.transcribed_text = self.client = self.whisper = None

    def transcribe_file(self):
        """Transcribe current audio content and store plain text."""

        if self.whisper is None:
            self.whisper = whisper.load_model(self.whisper_model)

        result = self.whisper.transcribe(self.audio_content, language=str(self.language))
        # Whisper returns a dict with 'text'; if not, fallback to str(result)
        text = result.get('text') if isinstance(result, dict) else None
        self.transcribed_text = text if isinstance(text, str) else str(result)
        return self.transcribed_text

    def restore_transcribed_text_with_gemini(self):
        """Use Gemini to enhance the transcribed text."""

        if self.client is None:
            self.client = genai.Client(api_key=GOOGLE_API_KEY)

        if not self.transcribed_text:
            raise ValueError("Transcribed text is empty. Run transcribe_file() first.")

        prompt = (
                "You are an assistant for restoring punctuation and case in transcribed speech text."
                "Correct punctuation, case, obvious typos and paragraphs. Don't add new information and don't "
                "retell. Keep the source language: " + str(self.language) + ". Return only the corrected text."
        )

        response = self.client.models.generate_content(
            model=self.gemini_model,
            contents=prompt
        )

        self.transcribed_text = response.text.strip()
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
