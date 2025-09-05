import whisper
from utilities.consts import WhisperModelsENUM, SupportedLanguagesCodesEnum, SupportedExtensionsEnum

class AudioToText:
    def __init__(self,
                 audio_file_content=None,
                 audio_file_path=None,
                 language=SupportedLanguagesCodesEnum.RU,
                 whisper_model=WhisperModelsENUM.TINY):

        self.language = language

        self.whisper_model = whisper_model

        self.audio_file_path = audio_file_path

        self._validate_init()

        if audio_file_content:
            self.audio_content = audio_file_content
        else:
            self.audio_content = self._get_audio_file_content()

        self.whisper = whisper.load_model(self.whisper_model)

    def transcribe_file(self):
        return self.whisper.transcribe(f=self.audio_content, language=self.language)

    def _get_audio_file_content(self):
        try:
            with open(self.audio_file_path, 'rb') as f:
                return f.read()
        except Exception as e:
            raise ValueError(f"Error reading audio file: {e}")

    def _validate_init(self):
        if self.language not in [lang.value for lang in SupportedLanguagesCodesEnum]:
            raise ValueError(f"Language '{self.language}' is not supported. Supported languages are: {[lang.value for lang in SupportedLanguagesCodesEnum]}")
        if not self.audio_file_path and not any(self.audio_file_path.endswith(ext.value) for ext in SupportedExtensionsEnum):
            raise ValueError(f"File extension is not supported. Supported extensions are: {[ext.value for ext in SupportedExtensionsEnum]}")
        if self.whisper_model not in [model.value for model in WhisperModelsENUM]:
            raise ValueError(f"Whisper model '{self.whisper_model}' is not supported. Supported models are: {[model.value for model in WhisperModelsENUM]}")
