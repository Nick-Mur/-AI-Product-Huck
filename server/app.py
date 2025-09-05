import os
import shutil
import uuid
import subprocess
from pathlib import Path
from typing import List

from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pdf2image import convert_from_path


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
    try:
        subprocess.run(
            [
                "libreoffice",
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(out_dir),
                str(pptx_path),
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Ошибка конвертации LibreOffice: {e.stderr.decode(errors='ignore')}")

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
        # If conversion fails, still expose the raw format
        return {"ok": True, "path": f"/images/{sessionId}/audio/{raw_path.name}", "format": safe_ext.lstrip('.')}

    return {"ok": True, "path": f"/images/{sessionId}/audio/{mp3_path.name}", "format": "mp3"}
