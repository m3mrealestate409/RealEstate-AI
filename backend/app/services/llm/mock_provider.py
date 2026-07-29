"""
Mock LLM provider - lets the ENTIRE engine run and be tested without any API key.

It does not invent facts: it echoes the grounding context it was given and
labels itself clearly, so tests can assert on deterministic output.
Constitution §8 (Hallucination): when given no context, it returns the
standard 'information not available' style message.
"""
from app.services.llm.base import LLMProvider, LLMResponse, Message


class MockLLMProvider(LLMProvider):
    name = "mock"

    def complete(
        self,
        *,
        system: str,
        messages: list[Message],
        temperature: float = 0.2,
        max_tokens: int = 1024,
        response_json: bool = False,
    ) -> LLMResponse:
        user_turn = next(
            (m.content for m in reversed(messages) if m.role == "user"), ""
        )
        # Grounding context is passed in the latest user turn by the orchestrator.
        has_context = "CONTEXT:" in user_turn and user_turn.split("CONTEXT:", 1)[1].strip()

        if not has_context:
            text = (
                "Information not available in the current knowledge base. "
                "[mock-provider: no grounding context supplied]"
            )
        else:
            text = (
                "[MOCK LLM RESPONSE - set LLM_PROVIDER=gemini with a real key for actual reasoning]\n"
                "Based only on the provided sources:\n"
                f"{user_turn.split('CONTEXT:', 1)[1].strip()[:800]}"
            )

        return LLMResponse(text=text, provider=self.name, model="mock")
