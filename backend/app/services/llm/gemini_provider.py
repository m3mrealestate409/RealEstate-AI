"""
Gemini provider. The SDK is imported LAZILY inside __init__ so the app boots
fine even when the package or key is absent (falls back to mock elsewhere).
"""
from app.config import settings
from app.services.llm.base import LLMProvider, LLMResponse, Message


class GeminiLLMProvider(LLMProvider):
    name = "gemini"

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        key = api_key or (settings.gemini_api_key if settings.gemini_ready else "")
        if not key or key == "PASTE_YOUR_KEY_HERE":
            raise RuntimeError(
                "Gemini API key not set. Add it via Admin → AI Settings or in .env."
            )
        import google.generativeai as genai  # lazy import

        genai.configure(api_key=key)
        self._genai = genai
        self._model_name = model or settings.llm_model

    def complete(
        self,
        *,
        system: str,
        messages: list[Message],
        temperature: float = 0.2,
        max_tokens: int = 2048,
        response_json: bool = False,
    ) -> LLMResponse:
        model = self._genai.GenerativeModel(
            self._model_name, system_instruction=system
        )
        # Map roles to Gemini's contents format.
        contents = []
        for m in messages:
            role = "model" if m.role == "assistant" else "user"
            contents.append({"role": role, "parts": [m.content]})

        gen_config = {"temperature": temperature, "max_output_tokens": max_tokens}
        # JSON mode: constrain the model to emit syntactically valid JSON. Without
        # it, the model occasionally returns malformed JSON (a missing comma, a
        # number with thousands-separators) that breaks parsing.
        if response_json:
            gen_config["response_mime_type"] = "application/json"

        resp = model.generate_content(contents, generation_config=gen_config)
        return LLMResponse(text=_extract_text(resp), provider=self.name, model=self._model_name)


def _extract_text(resp) -> str:
    """Safely pull text out of a Gemini response. Newer 'thinking' models can
    return a response whose `.text` accessor raises when the visible part is
    empty (e.g. finish_reason=MAX_TOKENS after using budget on reasoning), so
    we fall back to reading candidate parts directly."""
    try:
        t = resp.text
        if t:
            return t
    except Exception:
        pass
    try:
        parts = resp.candidates[0].content.parts
        return "".join(getattr(p, "text", "") for p in parts).strip()
    except Exception:
        return ""
