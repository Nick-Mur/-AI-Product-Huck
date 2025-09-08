import json
from typing import List, Dict, Any, Optional

from google import genai

from app.server.utilities.consts import GOOGLE_API_KEY, GeminiModelsEnum, SupportedLanguagesCodesEnum
from app.server.utilities.prompts import PROMPTS, PromptType


class AskGemini:
    def __init__(self,
                 system_prompt: str = "",
                 user_context: str = "",
                 model: GeminiModelsEnum = GeminiModelsEnum.gemini_2_5_flash,
                 file_parts: Optional[list] = None):

        if not GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY is not set in environment")

        self.client = genai.Client(api_key=GOOGLE_API_KEY)
        self.model = str(model)
        self.system_prompt = system_prompt.strip()
        self.user_context = (user_context or "").strip()
        # file_parts: list of {"file_uri": str, "mime_type": str}
        self.file_parts = file_parts or []

    def _gen(self, role: str = 'user', parts: List[Dict[str, Any]] = None):
        return self.client.models.generate_content(
            model=self.model,
            contents=[{
            "role": role,
            "parts": parts,
        }],
        )

    @staticmethod
    def _to_json(text: str, fallback: Dict[str, Any] | None = None) -> Dict[str, Any]:
        if fallback is None:
            fallback = {"feedback": "", "tips": []}
        if not text:
            return fallback
        s = text.strip()
        # try direct parse
        try:
            return json.loads(s)
        except Exception:
            pass
        # try to extract json block between braces
        try:
            start = s.find('{')
            end = s.rfind('}')
            if start != -1 and end != -1 and end > start:
                return json.loads(s[start:end + 1])
        except Exception:
            pass
        return fallback

    def review_slide(self, slide_index: int, polished_text: str) -> Dict[str, Any]:
        parts = []
        # Attach files first if present
        for f in self.file_parts:
            uri = f.get("file_uri")
            mt = f.get("mime_type")
            if uri and mt:
                parts.append({"file_data": {"file_uri": uri, "mime_type": mt}})

        parts += [
            {"text": f"[SYSTEM]\n{self.system_prompt}"},
            {"text": f"[CONTEXT]\n{self.user_context}"},
            {"text": f"[SLIDE {slide_index}]\n{polished_text}"},
            {"text": f"[REQUIREMENTS]\n{PROMPTS[PromptType.REVIEW_SLIDE]}"},
        ]

        res = self._gen(parts=parts)

        data = self._to_json(getattr(res, 'text', '') or '')
        # normalize tips length to 0..3 strings
        tips = data.get("tips")
        if not isinstance(tips, list):
            tips = []
        tips = [str(t).strip() for t in tips if str(t).strip()][:3]
        return {"feedback": str(data.get("feedback", "")).strip(), "tips": tips}

    def summarize(self, per_slide_findings: List[Dict[str, Any]], transcripts: Optional[List[str]] = None) -> Dict[str, Any]:

        slide_snippets = []
        for i, item in enumerate(per_slide_findings, start=1):
            fb = (item or {}).get("feedback", "").strip()
            tips = (item or {}).get("tips", [])
            tips_str = "; ".join([str(t).strip() for t in tips if str(t).strip()])
            if fb or tips_str:
                slide_snippets.append(f"Slide {i}: {fb} Tips: {tips_str}")

        transcript_note = ""
        if transcripts:
            transcript_note = "\n\nTRANSCRIPTS:\n" + "\n".join([t[:500] for t in transcripts if t])

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

        res = self._gen(parts=parts)
        data = self._to_json(getattr(res, 'text', '') or '')
        tips = data.get("tips")
        if not isinstance(tips, list):
            tips = []
        tips = [str(t).strip() for t in tips if str(t).strip()][:5]
        return {"feedback": str(data.get("feedback", "")).strip(), "tips": tips}

    def restore_transcribed_text(self,
                                 transcribed_text: str,
                                 language: SupportedLanguagesCodesEnum = SupportedLanguagesCodesEnum.RU):
        """Use Gemini to enhance punctuation, casing, and spacing of the transcribed text."""

        if self.client is None:
            if not GOOGLE_API_KEY:
                raise ValueError("GOOGLE_API_KEY is not set in environment")
            self.client = genai.Client(api_key=GOOGLE_API_KEY)

        if not transcribed_text:
            raise ValueError("Transcribed text is empty.")

        parts = [
            {"text": PROMPTS[PromptType.REVIEW_SLIDE].replace("{'language'}", language)},
            {"text": transcribed_text}]

        response = self._gen(parts=parts)

        transcribed_text = (response.text or "").strip()
        return transcribed_text
