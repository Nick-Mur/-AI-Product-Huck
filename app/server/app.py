import json
import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, List

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pdf2image import convert_from_path

from .AI.AskGemini import AskGemini
from .AI.AudioToText import AudioToText
from .utilities.consts import (
    ANALIZE_PDF,
    GeminiModelsEnum,
    SupportedLanguagesCodesEnum,
    WhisperModelsENUM,
)

BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="API конвертации слайдов")

# CORS for local dev
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve generated images
app.mount("/images", StaticFiles(directory=str(DATA_DIR)), name="images")


def _convert_pdf_to_pngs(pdf_path: Path, out_dir: Path) -> List[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    images = convert_from_path(str(pdf_path))
    paths: List[Path] = []
    for idx, img in enumerate(images, start=1):
        out_path = out_dir / f"slide-{idx}.png"
        img.save(out_path, "PNG")
        paths.append(out_path)
    return paths


def _convert_pptx_to_pdf(pptx_path: Path, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    # Use LibreOffice to convert PPTX -> PDF
    commands = [
        [
            "libreoffice",
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(out_dir),
            str(pptx_path),
        ],
        [
            "soffice",
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(out_dir),
            str(pptx_path),
        ],
    ]

    last_err = None
    for cmd in commands:
        try:
            subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            last_err = None
            break
        except FileNotFoundError as e:
            last_err = e
            continue
        except subprocess.CalledProcessError as e:
            raise HTTPException(status_code=500, detail=f"Ошибка конвертации LibreOffice: {e.stderr.decode(errors='ignore')}")

    if last_err:
        raise HTTPException(status_code=500, detail="LibreOffice (libreoffice/soffice) не установлен в контейнере")

    # Find resulting PDF (LibreOffice names it with same basename)
    pdf_path = out_dir / (pptx_path.stem + ".pdf")
    if not pdf_path.exists():
        # Try to find any PDF in out_dir if naming changed
        for p in out_dir.glob("*.pdf"):
            pdf_path = p
            break
    if not pdf_path.exists():
        raise HTTPException(status_code=500, detail="Преобразованный PDF не найден")
    return pdf_path


@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Файл не передан")

    ext = Path(file.filename).suffix.lower()
    if ext not in {".pdf", ".pptx"}:
        raise HTTPException(status_code=400, detail="Поддерживаются только файлы .pdf и .pptx")

    session_id = uuid.uuid4().hex
    session_dir = DATA_DIR / session_id
    upload_dir = session_dir / "upload"
    output_dir = session_dir / "slides"
    upload_dir.mkdir(parents=True, exist_ok=True)

    saved_path = upload_dir / file.filename
    # Save uploaded file
    with open(saved_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        if ext == ".pdf":
            _convert_pdf_to_pngs(saved_path, output_dir)
        else:
            # .pptx -> .pdf -> .png
            pdf_path = _convert_pptx_to_pdf(saved_path, upload_dir)
            _convert_pdf_to_pngs(pdf_path, output_dir)
    except HTTPException:
        # Bubble up known errors
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка конвертации: {e}")

    # Build URLs
    slides = sorted([p.name for p in output_dir.glob("slide-*.png")])
    slide_urls = [f"/images/{session_id}/slides/{name}" for name in slides]

    return JSONResponse(
        {
            "sessionId": session_id,
            "slides": slide_urls,
        }
    )


@app.get("/slides/{session_id}")
async def list_slides(session_id: str):
    output_dir = DATA_DIR / session_id / "slides"
    if not output_dir.exists():
        raise HTTPException(status_code=404, detail="Сессия не найдена")
    slides = sorted([p.name for p in output_dir.glob("slide-*.png")])
    slide_urls = [f"/images/{session_id}/slides/{name}" for name in slides]
    return {"sessionId": session_id, "slides": slide_urls}


@app.post("/audio")
async def upload_audio(
    sessionId: str = Form(...),
    slideIndex: int = Form(...),
    file: UploadFile = File(...),
):
    # Save audio per slide: data/<sessionId>/audio/slide-<index>.<ext>
    session_dir = DATA_DIR / sessionId
    if not session_dir.exists():
        raise HTTPException(status_code=404, detail="Сессия не найдена")

    audio_dir = session_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    ext = Path(file.filename).suffix or ".webm"
    safe_ext = ext if len(ext) <= 5 else ".webm"
    raw_path = audio_dir / f"slide-{int(slideIndex)}{safe_ext}"

    try:
        with open(raw_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Не удалось сохранить аудио: {e}")
    # Transcode to MP3 via ffmpeg to ensure broad compatibility
    mp3_path = audio_dir / f"slide-{int(slideIndex)}.mp3"
    try:
        # -y overwrite, -i input, -codec:a libmp3lame high quality, 128k bitrate
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(raw_path),
                "-codec:a",
                "libmp3lame",
                "-b:a",
                "128k",
                str(mp3_path),
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as e:
        # If conversion fails, still expose the raw format like before
        return {"ok": True, "path": f"/images/{sessionId}/audio/{raw_path.name}", "format": safe_ext.lstrip('.')}

    # Only if MP3 conversion succeeded, attempt transcription & enhancement
    transcript_json = audio_dir / f"slide-{int(slideIndex)}.json"
    try:
        at = AudioToText(
            audio_file_path=str(mp3_path),
            language=SupportedLanguagesCodesEnum.RU,
            whisper_model=WhisperModelsENUM.TINY,
            gemini_model=GeminiModelsEnum.gemini_2_5_flash,
        )
        raw_text = at.transcribe_file()
        polished_text = at.restore_transcribed_text_with_gemini()
        payload = {
            "raw": raw_text,
            "polished": polished_text,
            "lang": str(SupportedLanguagesCodesEnum.RU),
        }
        import json
        with open(transcript_json, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception:
        # Do not fail the audio upload on transcription error
        pass

    return {"ok": True, "path": f"/images/{sessionId}/audio/{mp3_path.name}", "format": "mp3"}


# ---- Review API (Gemini) ----

def _review_dir(session_id: str) -> Path:
    d = DATA_DIR / session_id / "review"
    d.mkdir(parents=True, exist_ok=True)
    return d


@app.post("/review/start")
async def review_start(
    sessionId: str = Form(...),
    mode: str = Form("per-slide"),
    extraInfo: str = Form("")
):
    session_dir = DATA_DIR / sessionId
    if not session_dir.exists():
        raise HTTPException(status_code=404, detail="Сессия не найдена")

    review_dir = _review_dir(sessionId)
    cfg = {
        "mode": mode,
        "extraInfo": extraInfo or "",
    }

    # Optionally upload session PDF to Gemini and persist a reference
    if ANALIZE_PDF:
        try:
            # try to find a PDF in upload subdir
            upload_dir = session_dir / "upload"
            pdf_candidates = list(upload_dir.glob("*.pdf")) if upload_dir.exists() else []
            if not pdf_candidates:
                # sometimes LibreOffice produced PDF used for images
                # also look for any PDF under session
                pdf_candidates = list(session_dir.rglob("*.pdf"))
            if pdf_candidates:
                from google import genai
                from mimetypes import guess_type
                client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
                pdf_path = pdf_candidates[0]
                up = client.files.upload(file=str(pdf_path))
                # Some versions expose uri/mime_type attributes
                file_uri = getattr(up, "uri", None) or getattr(up, "file_uri", None)
                mime_type = getattr(up, "mime_type", None) or guess_type(str(pdf_path))[0] or "application/pdf"
                if file_uri:
                    cfg["gemini_pdf"] = {
                        "file_uri": file_uri,
                        "mime_type": mime_type,
                        "name": pdf_path.name,
                    }
        except Exception:
            # PDF upload is optional; ignore failures
            pass
    with open(review_dir / "config.json", "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    return {"ok": True}


def _load_transcript(session_id: str, slide_index: int) -> str:
    session_dir = DATA_DIR / session_id
    audio_dir = session_dir / "audio"
    tpath = audio_dir / f"slide-{int(slide_index)}.json"
    if tpath.exists():
        try:
            with open(tpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            return (data.get("polished") or data.get("raw") or "").strip()
        except Exception:
            pass
    # On-demand transcribe if JSON absent or broken. Wait a bit for audio to appear.
    mp3_path = audio_dir / f"slide-{int(slide_index)}.mp3"
    audio_path = None
    for _ in range(40):  # ~10s with 0.25s steps
        if mp3_path.exists():
            audio_path = mp3_path
            break
        cand = list(audio_dir.glob(f"slide-{int(slide_index)}.*"))
        if cand:
            audio_path = cand[0]
            break
        time.sleep(0.25)
    if not audio_path:
        raise HTTPException(status_code=404, detail="Аудио для транскрибации не найдено")

    at = AudioToText(
        audio_file_path=str(audio_path),
        language=SupportedLanguagesCodesEnum.RU,
        whisper_model=WhisperModelsENUM.TINY,
        gemini_model=GeminiModelsEnum.gemini_2_5_flash,
    )
    raw_text = at.transcribe_file()
    polished = at.restore_transcribed_text_with_gemini()
    # persist for next time
    try:
        with open(tpath, "w", encoding="utf-8") as f:
            json.dump({"raw": raw_text, "polished": polished, "lang": str(SupportedLanguagesCodesEnum.RU)}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return polished or raw_text or ""


@app.post("/review/slide")
async def review_slide(
    sessionId: str = Form(...),
    slideIndex: int = Form(...),
):
    session_dir = DATA_DIR / sessionId
    if not session_dir.exists():
        raise HTTPException(status_code=404, detail="Сессия не найдена")

    review_dir = _review_dir(sessionId)
    cfg_path = review_dir / "config.json"
    extra = ""
    file_parts = []
    if cfg_path.exists():
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                extra = cfg.get("extraInfo") or ""
                pdf_meta = cfg.get("gemini_pdf")
                if pdf_meta and isinstance(pdf_meta, dict):
                    uri = pdf_meta.get("file_uri")
                    mt = pdf_meta.get("mime_type")
                    if uri and mt:
                        file_parts.append({"file_uri": uri, "mime_type": mt})
        except Exception:
            pass

    polished_text = _load_transcript(sessionId, int(slideIndex))

    system_prompt = "Оцени подачу и содержание доклада по слайду. Конкретика приветствуется."
    ag = AskGemini(system_prompt=system_prompt, user_context=extra, file_parts=file_parts)
    try:
        data = ag.review_slide(int(slideIndex), polished_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка оценки слайда: {e}")

    out_path = review_dir / f"slide-{int(slideIndex)}-review.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return data


@app.get("/review/summary")
async def review_summary(sessionId: str):
    session_dir = DATA_DIR / sessionId
    if not session_dir.exists():
        raise HTTPException(status_code=404, detail="Сессия не найдена")
    review_dir = _review_dir(sessionId)

    per_slide: List[Dict[str, Any]] = []
    # load all per-slide review results in order of slide number
    slide_files = sorted(review_dir.glob("slide-*-review.json"), key=lambda p: p.name)
    for p in slide_files:
        try:
            with open(p, "r", encoding="utf-8") as f:
                per_slide.append(json.load(f))
        except Exception:
            continue

    # also collect transcripts as optional context
    transcripts: List[str] = []
    audio_dir = session_dir / "audio"
    for tfile in sorted(audio_dir.glob("slide-*.json")):
        try:
            with open(tfile, "r", encoding="utf-8") as f:
                td = json.load(f)
                transcripts.append((td.get("polished") or td.get("raw") or "").strip())
        except Exception:
            continue

    cfg_path = review_dir / "config.json"
    extra = ""
    file_parts = []
    if cfg_path.exists():
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                extra = cfg.get("extraInfo") or ""
                pdf_meta = cfg.get("gemini_pdf")
                if pdf_meta and isinstance(pdf_meta, dict):
                    uri = pdf_meta.get("file_uri")
                    mt = pdf_meta.get("mime_type")
                    if uri and mt:
                        file_parts.append({"file_uri": uri, "mime_type": mt})
        except Exception:
            pass

    system_prompt = "Сделай итоговую оценку всей презентации: сильные и слабые стороны, ясность и структура."
    ag = AskGemini(system_prompt=system_prompt, user_context=extra, file_parts=file_parts)
    try:
        data = ag.summarize(per_slide_findings=per_slide, transcripts=transcripts if transcripts else None)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка итоговой оценки: {e}")

    with open(review_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return data


@app.get("/transcript")
async def get_transcript(sessionId: str, slideIndex: int):
    session_dir = DATA_DIR / sessionId
    if not session_dir.exists():
        raise HTTPException(status_code=404, detail="Сессия не найдена")
    audio_dir = session_dir / "audio"
    transcript_json = audio_dir / f"slide-{int(slideIndex)}.json"
    if transcript_json.exists():
        import json
        try:
            with open(transcript_json, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            raise HTTPException(status_code=500, detail="Не удалось прочитать транскрипт")
        return data

    # Optional: if JSON is absent but audio exists, try to transcribe on-demand
    mp3_path = audio_dir / f"slide-{int(slideIndex)}.mp3"
    raw_candidates = list(audio_dir.glob(f"slide-{int(slideIndex)}.*"))
    audio_path = mp3_path if mp3_path.exists() else (raw_candidates[0] if raw_candidates else None)
    if not audio_path or not audio_path.exists():
        raise HTTPException(status_code=404, detail="Аудио для этого слайда не найдено")

    try:
        at = AudioToText(
            audio_file_path=str(audio_path),
            language=SupportedLanguagesCodesEnum.RU,
            whisper_model=WhisperModelsENUM.TINY,
            gemini_model=GeminiModelsEnum.gemini_2_5_flash,
        )
        raw_text = at.transcribe_file()
        polished_text = at.restore_transcribed_text_with_gemini()
        payload = {
            "raw": raw_text,
            "polished": polished_text,
            "lang": str(SupportedLanguagesCodesEnum.RU),
        }
        import json
        with open(transcript_json, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return payload
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка транскрибации: {e}")
