# Code Style Guidelines / Руководство по стилю кода

## 1. General Principles / Общие принципы
- Follow [PEP 8](https://peps.python.org/pep-0008/) and Google Python Style Guide.
- Соблюдайте [PEP 8](https://peps.python.org/pep-0008/) и Google Python Style Guide.

## 2. Naming Conventions / Соглашения об именах
- Use `snake_case` for variables and functions; `PascalCase` for classes.
- Используйте `snake_case` для переменных и функций; `PascalCase` для классов.

## 3. Imports and Typing / Импорты и типизация
- Group imports as standard, third-party, and local; avoid unused imports.
- Группируйте импорты: стандартные, сторонние и локальные; избегайте неиспользуемых импортов.
- Add type hints for all public functions and methods.
- Добавляйте подсказки типов ко всем публичным функциям и методам.

## 4. Docstrings / Докстроки
- Every module, class, and function must have a docstring.
- Каждый модуль, класс и функция должны иметь докстроку.
- Start with an English summary, followed by the same text in Russian.
- Начинайте с краткого описания на английском, затем приведите тот же текст на русском.
- Include sections `Pipeline`, `Args`, `Returns`, and `Raises` when relevant.
- Включайте разделы `Pipeline`, `Args`, `Returns` и `Raises`, если это уместно.
- For each item in these sections, first write the English explanation, then the Russian translation.
- Для каждого элемента в этих разделах сначала пишите объяснение на английском, затем перевод на русском.

## 5. Comments / Комментарии
- Inline comments start with English text and then Russian translation separated by a comma.
- Встроенные комментарии начинаются с английского текста и затем русского перевода, разделённого запятой.

## 6. Function Structure / Структура функций
- Use numbered steps in docstring `Pipeline` sections to outline processes.
- Используйте нумерованные шаги в разделе `Pipeline` докстрок для описания процессов.

## 7. Error Handling / Обработка ошибок
- Raise specific exceptions with clear messages in English and Russian when validating inputs.
- Выбрасывайте конкретные исключения с понятными сообщениями на английском и русском при проверке входных данных.

## 8. Line Length / Длина строк
- Limit code lines to 88 characters and docstring lines to 88 characters to accommodate translations.
- Ограничивайте длину строк кода и докстрок 88 символами, чтобы учитывать переводы.

## 9. Linting and Testing / Линтинг и тестирование
- Run available linters and tests before committing.
- Запускайте доступные линтеры и тесты перед коммитом.

Guidelines are based on the existing style in `app/server/AI`. / Рекомендации основаны на существующем стиле в `app/server/AI`.
