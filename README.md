# AI Slides Reviewer (PDF/PPTX → PNG + Audio → Text → Gemini)

Проект состоит из двух контейнеров (frontend + server): React UI и FastAPI backend. Позволяет загрузить презентацию, вести прогон с записью аудио по каждому слайду, автоматически расшифровать речь (Whisper), улучшить текст (Gemini), получить AI‑оценку каждого слайда и итог всей презентации.

Основные возможности
- Загрузка `.pdf` или `.pptx`.
- Конвертация PPTX → PDF (LibreOffice) → PNG (Poppler/pdf2image).
- Прогон с отсчётом и записью аудио по каждому слайду, навигация стрелками.
- Автотранскрибация (Whisper) + улучшение пунктуации/регистра (Gemini).
- Отчёт по слайду: аудио, транскрипт, AI‑фидбек и до 3 подсказок.
- Итоговый обзор: аудио по каждому слайду, полный фидбек от AI и до 5 подсказок.

Сервисы
- `frontend` (CRA dev server, HTTPS): работает на `3000`, проксирует API на `server:5000` (см. `frontend/package.json` → `proxy`).
- `server` (FastAPI + Uvicorn): работает на `5000`, статически раздаёт изображения и аудио по `/images/...`.

Быстрый старт
1. Создайте `.env` в корне (см. ниже). Пример:
   - `GOOGLE_API_KEY=...`
   - `AnalizePDF=true`  # опционально: прикладывать исходный PDF к запросам в Gemini
2. Соберите и запустите: `docker-compose up --build`
3. Откройте: `http://localhost:3000`

Переменные окружения
- `GOOGLE_API_KEY` — API‑ключ Google для `google-genai` (Gemini).
- `AnalizePDF` — если `true/1/yes`, при старте оценки презентации сервер загружает PDF в Gemini и прикладывает его ко всем запросам (даёт дополнительный контекст).

API (основные маршруты)
- `POST /upload` — загрузка `.pdf`/`.pptx`; ответ: `{ sessionId, slides: ["/images/<sessionId>/slides/slide-1.png", ...] }`.
- `GET /slides/{session_id}` — список PNG‑слайдов.
- `POST /audio` — загрузка аудио для слайда; конвертирует в mp3, запускает транскрибацию и улучшение, сохраняет JSON с текстом.
- `GET /transcript?sessionId&slideIndex` — получение транскрипта (если нет — создаёт on‑demand).
- `POST /review/start` — старт рецензии (mode: `per-slide`|`full`, extraInfo: произвольный текст).
- `POST /review/slide` — AI‑оценка одного слайда; JSON: `{ feedback, tips[] }`.
- `GET /review/summary?sessionId` — итог по всей презентации; JSON: `{ feedback, tips[] }`.

Технологии и зависимости (server)
- FastAPI, Uvicorn, pdf2image (Poppler), LibreOffice (soffice) для PPTX→PDF, ffmpeg для аудио, Whisper (openai-whisper), Google GenAI (Gemini).
- В Dockerfile устанавливаются `libreoffice`, `poppler-utils`, `ffmpeg` и необходимые шрифты.

Данные
- Все сессионные артефакты пишутся в `server/data/<sessionId>` и пробрасываются через volume `server_data`.
  - `slides/slide-*.png` — изображения слайдов
  - `audio/slide-*.mp3` — аудио
  - `audio/slide-*.json` — транскрипт (+ улучшенный текст)
  - `review/*.json` — результаты AI‑оценок

Разработка локально (опционально)
- Фронтенд: `cd frontend && npm i && npm start` (CRA на 3000, HTTPS). Прокси на API уже прописан.
- Бэкенд: `cd server && pip install -r requirements.txt && uvicorn app:app --reload --host 0.0.0.0 --port 5000`.

Примечания
- Для CPU‑окружений Whisper запускается в FP32 (предупреждение FP16 подавлено).
- Если оценка слайда уезжает раньше сохранения аудио, сервер ждёт появление файла до ~10 секунд.
