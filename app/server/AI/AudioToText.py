"""Transcribe audio with Whisper and refine text via Gemini.

Транскрибирует аудио с помощью Whisper и улучшает текст через Gemini.
"""

import whisper
import warnings
from app.server.utilities.consts import (
    WhisperModelsENUM,
    SupportedLanguagesCodesEnum,
    SupportedExtensionsEnum,
    GeminiModelsEnum,
)
from AskGemini import AskGemini


class AudioToText:
    def __init__(
        self,
        audio_file_content=None,
        audio_file_path=None,
        language=SupportedLanguagesCodesEnum.RU,
        whisper_model=WhisperModelsENUM.TINY,
        gemini_model=GeminiModelsEnum.gemini_2_5_flash,
    ):
        """Configure audio transcription parameters.

        Настраивает параметры транскрибации аудио.

        Pipeline:
            1. Store initialization parameters.
               Сохраняем параметры инициализации.
            2. Validate language, models, and inputs.
               Проверяем язык, модели и входные данные.
            3. Prepare placeholders for future processing.
               Подготавливаем переменные-заглушки для дальнейшей обработки.

        Args:
            audio_file_content (bytes | None): In-memory audio data.
                Аудиоданные в памяти.
            audio_file_path (str | None): Path to the audio file.
                Путь к аудиофайлу.
            language (SupportedLanguagesCodesEnum): Target transcription
                language.
                Целевой язык транскрибации.
            whisper_model (WhisperModelsENUM): Selected Whisper model.
                Выбранная модель Whisper.
            gemini_model (GeminiModelsEnum): Gemini model for text
                restoration.
                Модель Gemini для восстановления текста.

        Returns:
            None
            Ничего

        Raises:
            ValueError: If inputs or models are invalid.
            ValueError: Если входные данные или модели некорректны.
        """

        # Step 1: Store provided configuration
        # Шаг 1: Сохраняем переданную конфигурацию
        self.language = language
        self.whisper_model = whisper_model
        self.audio_file_path = audio_file_path
        self.audio_content = audio_file_content
        self.gemini_model = gemini_model

        # Step 2: Validate initial parameters
        # Шаг 2: Проверяем начальные параметры
        self._validate_init()

        # Step 3: Ensure audio content placeholder exists
        # Шаг 3: Обеспечиваем наличие заглушки аудиоконтента
        if self.audio_content is None and self.audio_file_path:
            self.audio_content = None

        # Step 4: Prepare placeholders for runtime objects
        # Шаг 4: Подготавливаем заглушки для объектов выполнения
        self.transcribed_text = self.client = self.whisper = None

    def transcribe_file(self):
        """Transcribe the provided audio file with Whisper.

        Транскрибирует предоставленное аудио с помощью Whisper.

        Pipeline:
            1. Load the Whisper model if not already loaded.
               Загружаем модель Whisper при необходимости.
            2. Determine the audio source (path or in-memory).
               Определяем источник аудио (путь или память).
            3. Filter CPU warnings and run transcription.
               Фильтруем предупреждения CPU и запускаем транскрибацию.
            4. Extract and store the resulting text.
               Извлекаем и сохраняем полученный текст.

        Returns:
            str: Transcribed text.
            str: Транскрибированный текст.

        Raises:
            ValueError: If no audio source is available.
            ValueError: Если отсутствует источник аудио.
        """

        # Step 1: Load Whisper model if needed
        # Шаг 1: Загружаем модель Whisper при необходимости
        if self.whisper is None:
            self.whisper = whisper.load_model(str(self.whisper_model))

        # Step 2: Determine audio source
        # Шаг 2: Определяем источник аудио
        source = (
            self.audio_file_path
            if self.audio_file_path
            else self.audio_content
        )
        if source is None:
            raise ValueError("No audio provided for transcription")

        # Step 3: Suppress FP16 warning on CPU
        # Шаг 3: Подавляем предупреждение FP16 на CPU
        warnings.filterwarnings(
            "ignore", message=r".*FP16 is not supported on CPU.*"
        )

        # Step 4: Run transcription
        # Шаг 4: Запускаем транскрибацию
        result = self.whisper.transcribe(
            source, language=str(self.language), fp16=False
        )

        # Step 5: Extract text and store result
        # Шаг 5: Извлекаем текст и сохраняем результат
        text = result.get('text') if isinstance(result, dict) else None
        self.transcribed_text = text if isinstance(text, str) else str(result)
        return self.transcribed_text

    def restore_transcribed_text_with_gemini(self):
        """Improve transcription text using Gemini.

        Улучшает текст транскрипции с помощью Gemini.

        Pipeline:
            1. Initialize Gemini client.
               Инициализируем клиента Gemini.
            2. Restore text formatting and punctuation.
               Восстанавливаем форматирование и пунктуацию текста.
            3. Return refined transcription.
               Возвращаем улучшенную транскрипцию.

        Returns:
            str: Enhanced transcribed text.
            str: Улучшенный транскрибированный текст.
        """

        # Step 1: Initialize Gemini client
        # Шаг 1: Инициализируем клиента Gemini
        gemini = AskGemini(model=self.gemini_model)

        # Step 2: Restore transcription via Gemini
        # Шаг 2: Восстанавливаем транскрипт через Gemini
        self.transcribed_text = gemini.restore_transcribed_text(
            transcribed_text=self.transcribed_text, language=self.language
        )

        # Step 3: Return processed text
        # Шаг 3: Возвращаем обработанный текст
        return self.transcribed_text

    def _get_audio_file_content(self):
        """Read audio file content from disk.

        Считывает содержимое аудиофайла с диска.

        Pipeline:
            1. Open file in binary mode.
               Открываем файл в бинарном режиме.
            2. Read and return bytes.
               Читаем и возвращаем байты.

        Returns:
            bytes: Raw audio data.
            bytes: Исходные аудиоданные.

        Raises:
            ValueError: If file reading fails.
            ValueError: Если чтение файла не удалось.
        """

        # Step 1: Open the file safely
        # Шаг 1: Безопасно открываем файл
        try:
            with open(self.audio_file_path, 'rb') as f:
                # Step 2: Read and return content
                # Шаг 2: Читаем и возвращаем содержимое
                return f.read()
        except Exception as e:
            # Step 3: Raise error on failure
            # Шаг 3: Выбрасываем ошибку при неудаче
            raise ValueError(f"Error reading audio file: {e}")

    def _validate_init(self):
        """Validate initialization parameters.

        Проверяет параметры инициализации.

        Pipeline:
            1. Confirm supported language.
               Подтверждаем поддерживаемый язык.
            2. Confirm supported Whisper model.
               Подтверждаем поддерживаемую модель Whisper.
            3. Confirm supported Gemini model.
               Подтверждаем поддерживаемую модель Gemini.
            4. Ensure audio content or path is provided.
               Убеждаемся в наличии аудиоданных или пути.
            5. Validate file extension if path is given.
               Проверяем расширение файла, если указан путь.

        Returns:
            None
            Ничего

        Raises:
            ValueError: If validation fails.
            ValueError: Если проверка не проходит.
        """

        # Step 1: Validate language
        # Шаг 1: Проверяем язык
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

        # Step 2: Validate Whisper model
        # Шаг 2: Проверяем модель Whisper
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

        # Step 3: Validate Gemini model
        # Шаг 3: Проверяем модель Gemini
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

        # Step 4: Ensure content or path provided
        # Шаг 4: Убеждаемся в наличии контента или пути
        if self.audio_content is None and not self.audio_file_path:
            raise ValueError(
                "Provide either 'audio_file_content' or a valid "
                "'audio_file_path'."
            )

        # Step 5: Validate file extension if path exists
        # Шаг 5: Проверяем расширение файла, если путь указан
        if self.audio_file_path and not self.audio_file_path.endswith(
            tuple(SupportedExtensionsEnum)
        ):
            supported_exts = ", ".join(map(str, SupportedExtensionsEnum))
            raise ValueError(
                "File extension is not supported. Supported extensions are: "
                f"{supported_exts}"
            )
