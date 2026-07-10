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
        max_tokens: int = 1024,
    ) -> LLMResponse:
        model = self._genai.GenerativeModel(
            self._model_name, system_instruction=system
        )
        # Map roles to Gemini's contents format.
        contents = []
        for m in messages:
            role = "model" if m.role == "assistant" else "user"
            contents.append({"role": role, "parts": [m.content]})

        resp = model.generate_content(
            contents,
            generation_config={
                "temperature": temperature,
                "max_output_tokens": max_tokens,
            },
        )
        text = getattr(resp, "text", "") or ""
        return LLMResponse(text=text, provider=self.name, model=self._model_name)
