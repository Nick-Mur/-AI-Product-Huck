# AI Slides Reviewer (PDF/PPTX → PNG + Audio → Text → Gemini)

Инструмент для прогона презентаций с записью голоса и автоматической обратной связью от ИИ. Загружает PDF/PPTX, рендерит слайды в PNG, записывает аудио по каждому слайду, транскрибирует (Whisper), улучшает текст (Gemini) и формирует рекомендации по каждому слайду и по всей презентации.

Архитектура
- `frontend` — Create React App dev‑сервер по HTTPS на `3000`, проксирует API на бэкенд (см. `app/frontend/package.json: proxy`).
- `server` — FastAPI на `5000`, раздаёт статику `/images/...` с данными сессий.
- `nginx` — TLS‑терминация и реверс‑прокси на `80/443`, проксирует фронтенд и API.

Быстрый старт
- Требования: Docker и Docker Compose.
- Подготовьте `.env` (не коммитьте реальные ключи):
  - `GOOGLE_API_KEY=your-key`
  - `AnalizePDF=false`  # опционально: прикладывать исходный PDF к запросам в Gemini
  - `DISABLE_TRANSCRIPTION=false`  # опционально: отключить Whisper на слабых хостах
- Сертификаты для Nginx (если нет реальных):
  - Положите файлы в `app/nginx/certs`: `fullchain.pem` и `certificate.pem`.
  - Для локали можно сгенерировать самоподписанные:
    - Linux/macOS: `openssl req -x509 -nodes -newkey rsa:2048 -keyout app/nginx/certs/certificate.pem -out app/nginx/certs/fullchain.pem -days 365 -subj "/CN=localhost"`
- Запустите: `docker-compose up --build`
- Откройте: `https://localhost` (или ваш домен)

Возможности
- Загрузка `.pdf` или `.pptx` (PPTX → PDF через LibreOffice → PNG через Poppler/pdf2image).
- Прогон презентации с записью аудио по каждому слайду, навигация стрелками.
- Автотранскрибация (Whisper) + улучшение текста (Gemini).
- Отчёты: по слайдам (до 3 советов) и общий итог (до 5 советов).

Переменные окружения
- `GOOGLE_API_KEY` — ключ для `google-genai` (Gemini).
- `AnalizePDF` — если `true/1/yes`, при запуске рецензии сервер прикрепляет исходный PDF к запросам Gemini.
- `DISABLE_TRANSCRIPTION` — если `true/1/yes`, Whisper не запускается; полезно на хостах с ограниченной RAM/CPU.

API (основные маршруты)
- `POST /upload` — загрузка `.pdf`/`.pptx`; ответ: `{ sessionId, slides: ["/images/<sessionId>/slides/slide-1.png", ...] }`.
- `GET /slides/{session_id}` — список PNG‑слайдов.
- `POST /audio` — загрузка аудио; транскодирование в mp3, опциональная транскрибация и сохранение `slide-*.json`.
- `GET /transcript?sessionId&slideIndex` — получить/сгенерировать транскрипт.
- `POST /review/start` — старт рецензии (mode: `per-slide`|`full`, extraInfo: произвольный текст).
- `POST /review/slide` — оценка одного слайда.
- `GET /review/summary?sessionId` — итог по всей презентации.

Данные и хранение
- Все артефакты сессии: `/app/data/<sessionId>` внутри `server` (volume `server_data` в `docker-compose.yml:20-21`).
  - `slides/slide-*.png` — изображения
  - `audio/slide-*.mp3` и `audio/slide-*.json` — аудио и транскрипт
  - `review/*.json` — результаты AI‑оценки
- Статика доступна по `/images/...` (см. `app/server/app.py:40`).

Сетевое взаимодействие и прокси
- Nginx принимает HTTP→HTTPS и проксирует фронтенд и API:
  - Редирект 80→443 (см. `app/nginx/default.conf:7`).
  - Сертификаты: `ssl_certificate` и `ssl_certificate_key` (см. `app/nginx/default.conf:18` и `app/nginx/default.conf:19`).
  - Маршрутизация API: `/images`, `/upload|audio|transcript`, `/review|slides` (см. `app/nginx/default.conf:26`, `app/nginx/default.conf:39`, `app/nginx/default.conf:49`).
  - Фронтенд: прокси на CRA `https://frontend:3000` с отключенной проверкой upstream‑сертификата (см. `app/nginx/default.conf:61`).
- Порты/сервисы: см. `docker-compose.yml:3-37`.

Локальная разработка
- Фронтенд: `cd app/frontend && npm i && npm start` (CRA на 3000, HTTPS; прокси на API указан в `app/frontend/package.json`).
- Бэкенд: `cd app/server && pip install -r requirements.txt && uvicorn app:app --reload --host 0.0.0.0 --port 5000`.

Технологический стек (server)
- FastAPI, Uvicorn, pdf2image (Poppler), LibreOffice (soffice), ffmpeg, Whisper (openai-whisper), Google GenAI (Gemini).
- Установка системных пакетов в `app/server/Dockerfile`.

Примечания и советы
- На CPU Whisper работает в FP32; предупреждение FP16 подавлено.
- Если аудио ещё пишется, сервер ожидает появления файла до ~10 сек перед on‑demand транскрибацией.
- Для прод‑режима стоит собирать фронтенд (`npm run build`) и раздавать статику Nginx, вместо dev‑сервера CRA.
- Не храните реальные секреты в репозитории; сгенерируйте новый ключ, если `.env` оказался в истории.
