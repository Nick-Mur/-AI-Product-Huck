import json
from typing import List, Dict, Any, Optional

from google import genai

from app.server.utilities.consts import (
    GOOGLE_API_KEY,
    GeminiModelsEnum,
    SupportedLanguagesCodesEnum,
)
from app.server.utilities.prompts import PROMPTS, PromptType


class AskGemini:
    """Wrapper for Gemini model interactions.

    Обёртка для взаимодействия с моделью Gemini.
    """

    def __init__(self,
                 system_prompt: str = "",
                 user_context: str = "",
                 model: GeminiModelsEnum = GeminiModelsEnum.gemini_2_5_flash,
                 file_parts: Optional[list] = None):
        """Initialize Gemini client and context.

        Инициализировать клиент Gemini и контекст.

        Pipeline:

            1. Validate API key.
               Проверить API ключ.

            2. Create client and store parameters.
               Создать клиента и сохранить параметры.

        Args:

            system_prompt (str):
                Global system instructions.
                Глобальные системные инструкции.

            user_context (str):
                Additional user context.
                Дополнительный пользовательский контекст.

            model (GeminiModelsEnum):
                Gemini model to use.
                Используемая модель Gemini.

            file_parts (Optional[list]):
                List of file descriptors.
                Список описаний файлов.

        Raises:

            ValueError:
                Missing API key.
                Отсутствует API ключ.
        """

        # Step 1: Ensure API key is available
        # Шаг 1: Убедиться, что API ключ доступен
        if not GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY is not set in environment")

        # Step 2: Initialize client and store settings
        # Шаг 2: Инициализировать клиента и сохранить настройки
        self.client = genai.Client(api_key=GOOGLE_API_KEY)
        self.model = str(model)
        self.system_prompt = system_prompt.strip()
        self.user_context = (user_context or "").strip()
        # file_parts: list of {"file_uri": str, "mime_type": str}
        self.file_parts = file_parts or []

    def _gen(self, role: str = 'user', parts: List[Dict[str, Any]] = None):
        """Send prompt parts to Gemini model.

        Отправить части запроса модели Gemini.

        Pipeline:

            1. Build request payload.
               Сформировать полезную нагрузку.

            2. Call model and return response.
               Вызвать модель и вернуть ответ.

        Args:

            role (str):
                Role of the sender.
                Роль отправителя.

            parts (List[Dict[str, Any]]):
                Content parts for the model.
                Части контента для модели.

        Returns:
            Any:
                Response from Gemini.
                Ответ от Gemini.

        Raises:

            Exception:
                Propagated client errors.
                Ошибки клиента пробрасываются.
        """

        # Step 1: Build payload for the request
        # Шаг 1: Сформировать полезную нагрузку запроса
        payload = [{"role": role, "parts": parts}]

        # Step 2: Send request to Gemini and return response
        # Шаг 2: Отправить запрос Gemini и вернуть ответ
        return self.client.models.generate_content(
            model=self.model,
            contents=payload,
        )

    @staticmethod
    def _to_json(
            text: str,
            fallback: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Convert text to JSON with graceful degradation.

        Преобразовать текст в JSON с плавным ухудшением.

        Pipeline:

            1. Use provided fallback if conversion fails.
               Использовать запасной вариант при сбое конвертации.

            2. Try direct JSON parsing.
               Попробовать прямой парсинг JSON.

            3. Try extracting JSON block between braces.
               Попробовать извлечь JSON между фигурными скобками.

            4. Return fallback on failure.
               Вернуть запасной вариант при неудаче.

        Args:

            text (str):
                Textual response from Gemini.
                Текстовый ответ от Gemini.

            fallback (Optional[Dict[str, Any]]):
                Value if parsing fails.
                Значение при неудачном парсинге.

        Returns:

            Dict[str, Any]:
                Parsed data or fallback.
                Разобранные данные или запасной вариант.
        """

        # Step 1: Prepare fallback structure
        # Шаг 1: Подготовить запасную структуру
        if fallback is None:
            fallback = {"feedback": "", "tips": []}
        if not text:
            return fallback

        # Step 2: Attempt direct JSON parsing
        # Шаг 2: Попытаться напрямую разобрать JSON
        s = text.strip()
        try:
            return json.loads(s)
        except Exception:
            pass

        # Step 3: Extract JSON block between braces
        # Шаг 3: Извлечь блок JSON между фигурными скобками
        try:
            start = s.find('{')
            end = s.rfind('}')
            if start != -1 and end != -1 and end > start:
                return json.loads(s[start:end + 1])
        except Exception:
            pass

        # Step 4: Return fallback when parsing fails
        # Шаг 4: Вернуть запасное значение при сбое парсинга
        return fallback

    def review_slide(
            self, slide_index: int, polished_text: str) -> Dict[str, Any]:
        """Generate feedback for a single slide.

        Сгенерировать отзыв для отдельного слайда.

        Pipeline:

            1. Attach optional files.
               Прикрепить необязательные файлы.

            2. Compose prompt with system data and slide text.
               Сформировать запрос из системных данных и текста слайда.

            3. Call Gemini model.
               Вызвать модель Gemini.

            4. Parse and normalize response.
               Разобрать и нормализовать ответ.

        Args:

            slide_index (int):
                Position of the slide.
                Номер слайда.

            polished_text (str):
                Prepared transcription of the slide.
                Подготовленный текст слайда.

        Returns:

            Dict[str, Any]:
                Feedback and up to three tips.
                Отзыв и до трёх советов.

        Raises:

            Exception:
                Propagated Gemini client errors.
                Пробрасываемые ошибки клиента Gemini.
        """

        # Step 1: Attach files if provided
        # Шаг 1: Прикрепить файлы при наличии
        parts = []
        for f in self.file_parts:
            uri = f.get("file_uri")
            mt = f.get("mime_type")
            if uri and mt:
                parts.append({"file_data": {"file_uri": uri, "mime_type": mt}})

        # Step 2: Add prompt sections
        # Шаг 2: Добавить части запроса
        parts += [
            {"text": f"[SYSTEM]\n{self.system_prompt}"},
            {"text": f"[CONTEXT]\n{self.user_context}"},
            {"text": f"[SLIDE {slide_index}]\n{polished_text}"},
            {"text": f"[REQUIREMENTS]\n{PROMPTS[PromptType.REVIEW_SLIDE]}"},
        ]

        # Step 3: Request review from Gemini
        # Шаг 3: Запросить отзыв у Gemini
        res = self._gen(parts=parts)

        # Step 4: Parse response and normalize tips
        # Шаг 4: Разобрать ответ и нормализовать советы
        data = self._to_json(getattr(res, 'text', '') or '')
        tips = data.get("tips")
        if not isinstance(tips, list):
            tips = []
        tips = [str(t).strip() for t in tips if str(t).strip()][:3]
        return {
            "feedback": str(data.get("feedback", "")).strip(),
            "tips": tips,
        }

    def summarize(
            self,
            per_slide_findings: List[Dict[str, Any]],
            transcripts: Optional[List[str]] = None) -> Dict[str, Any]:
        """Create overall summary for the presentation.

        Сформировать общий обзор презентации.

        Pipeline:

            1. Build snippets from per-slide findings.
               Сформировать фрагменты из данных по слайдам.

            2. Append optional transcripts.
               Добавить при необходимости транскрипты.

            3. Attach files and construct prompt.
               Прикрепить файлы и составить запрос.

            4. Call Gemini model and parse response.
               Вызвать модель Gemini и разобрать ответ.

            5. Normalize tips length.
               Нормализовать длину советов.

        Args:

            per_slide_findings (List[Dict[str, Any]]):
                Results for each slide.
                Результаты для каждого слайда.

            transcripts (Optional[List[str]]):
                Optional slide transcripts.
                Необязательные транскрипты слайдов.

        Returns:

            Dict[str, Any]:
                Summary feedback and up to five tips.
                Сводный отзыв и до пяти советов.

        Raises:

            Exception:
                Propagated Gemini client errors.
                Пробрасываемые ошибки клиента Gemini.
        """

        # Step 1: Build snippets from slide findings
        # Шаг 1: Сформировать фрагменты из данных по слайдам
        slide_snippets = []
        for i, item in enumerate(per_slide_findings, start=1):
            fb = (item or {}).get("feedback", "").strip()
            tips = (item or {}).get("tips", [])
            tips_str = "; ".join([
                str(t).strip() for t in tips if str(t).strip()
            ])
            if fb or tips_str:
                slide_snippets.append(f"Slide {i}: {fb} Tips: {tips_str}")

        # Step 2: Prepare transcript note if provided
        # Шаг 2: Подготовить заметку по транскриптам при наличии
        transcript_note = ""
        if transcripts:
            transcript_note = (
                "\n\nTRANSCRIPTS:\n" +
                "\n".join([t[:500] for t in transcripts if t])
            )

        # Step 3: Attach files and assemble prompt
        # Шаг 3: Прикрепить файлы и собрать запрос
        parts = []
        for f in self.file_parts:
            uri = f.get("file_uri")
            mt = f.get("mime_type")
            if uri and mt:
                parts.append({"file_data": {"file_uri": uri, "mime_type": mt}})

        parts += [
            {"text": f"[SYSTEM]\n{self.system_prompt}"},
            {"text": f"[CONTEXT]\n{self.user_context}"},
            {"text": f"[PER_SLIDE]\n" + "\n".join(slide_snippets)},
            {"text": transcript_note},
            {"text": f"[REQUIREMENTS]\n{PROMPTS[PromptType.SUMMARIZE]}"},
        ]

        # Step 4: Generate summary via Gemini
        # Шаг 4: Сгенерировать сводку через Gemini
        res = self._gen(parts=parts)
        data = self._to_json(getattr(res, 'text', '') or '')

        # Step 5: Normalize tips to at most five items
        # Шаг 5: Нормализовать советы максимум до пяти пунктов
        tips = data.get("tips")
        if not isinstance(tips, list):
            tips = []
        tips = [str(t).strip() for t in tips if str(t).strip()][:5]
        return {
            "feedback": str(data.get("feedback", "")).strip(),
            "tips": tips,
        }

    def restore_transcribed_text(
            self,
            transcribed_text: str,
            language: SupportedLanguagesCodesEnum = (
                SupportedLanguagesCodesEnum.RU
            ),
    ):
        """Refine raw transcription using Gemini.

        Улучшить сырую транскрипцию с помощью Gemini.

        Pipeline:

            1. Ensure client is initialized.
               Убедиться, что клиент инициализирован.

            2. Validate provided text.
               Проверить предоставленный текст.

            3. Build request with language instructions.
               Собрать запрос с инструкциями по языку.

            4. Call Gemini and retrieve refined text.
               Вызвать Gemini и получить улучшенный текст.

        Args:

            transcribed_text (str):
                Raw text to polish.
                Исходный текст для улучшения.

            language (SupportedLanguagesCodesEnum): Language of transcription.
                Язык транскрипции.

        Returns:

            str:
                Text with improved formatting.
                Текст с улучшенным форматированием.

        Raises:

            ValueError:
                Missing API key or empty text.
                Отсутствует API ключ или пустой текст.

            Exception:
                Propagated Gemini client errors.
                Пробрасываемые ошибки клиента Gemini.
        """

        # Step 1: Ensure client exists
        # Шаг 1: Убедиться, что клиент существует
        if self.client is None:
            if not GOOGLE_API_KEY:
                raise ValueError("GOOGLE_API_KEY is not set in environment")
            self.client = genai.Client(api_key=GOOGLE_API_KEY)

        # Step 2: Validate input text
        # Шаг 2: Проверить входной текст
        if not transcribed_text:
            raise ValueError("Transcribed text is empty.")

        # Step 3: Build prompt parts
        # Шаг 3: Собрать части запроса
        parts = [
            {"text": PROMPTS[PromptType.REVIEW_SLIDE].replace("{'language'}", language)},
            {"text": transcribed_text},
        ]

        # Step 4: Request refinement from Gemini
        # Шаг 4: Запросить улучшение у Gemini
        response = self._gen(parts=parts)

        # Step 5: Return refined text
        # Шаг 5: Вернуть улучшенный текст
        transcribed_text = (response.text or "").strip()
        return transcribed_text
