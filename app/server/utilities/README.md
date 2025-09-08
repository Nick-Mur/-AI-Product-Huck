# Utilities package / Пакет Utilities

## Overview / Обзор
This directory collects helper modules used by the server to centralize shared configuration and prompt templates. It currently offers enumerations for AI models, supported language codes, and transcription formats as well as standard prompts for Gemini interactions.
Эта директория содержит вспомогательные модули, используемые сервером для централизованного хранения общей конфигурации и шаблонов подсказок. Здесь находятся перечисления доступных моделей ИИ, поддерживаемых языков и форматов транскрипции, а также стандартные запросы для взаимодействия с Gemini.

## Usage in the project / Использование в проекте
- `consts.py` supplies enums and settings that are imported by `app.py`, `AI/AudioToText.py`, and `AI/AskGemini.py` to configure transcription, language selection, and Gemini API access.
- `prompts.py` defines `PromptType` and the `PROMPTS` dictionary. `AI/AskGemini.py` uses these templates when generating feedback, summaries, or restored text.
`consts.py` предоставляет перечисления и настройки, которые импортируются `app.py`, `AI/AudioToText.py` и `AI/AskGemini.py` для конфигурации транскрипции, выбора языка и доступа к Gemini.
`prompts.py` определяет `PromptType` и словарь `PROMPTS`. `AI/AskGemini.py` использует эти шаблоны для генерации отзывов, итоговых оценок или восстановления текста.

## Updating modules / Обновление модулей
- To support new models, languages, or file extensions, extend the relevant enums in `consts.py` and update dependent imports.
- When changing prompt wording or adding new prompt types, modify `prompts.py` and keep `PromptType` keys synchronized with the `PROMPTS` dictionary.
- Adjust environment variables referenced in `consts.py` (e.g., `GOOGLE_API_KEY`, `AnalizePDF`) through `.env` files.
- After modifying utilities, run the project's tests to confirm nothing breaks.
Чтобы добавить новые модели, языки или расширения, расширьте соответствующие перечисления в `consts.py` и обновите связанные импорты.
При изменении формулировок подсказок или добавлении новых типов обновляйте `prompts.py` и следите, чтобы ключи `PromptType` соответствовали словарю `PROMPTS`.
Настраивайте переменные окружения, используемые в `consts.py` (например, `GOOGLE_API_KEY`, `AnalizePDF`) через файлы `.env`.
После внесения изменений запустите тесты проекта, чтобы убедиться, что ничего не сломалось.
