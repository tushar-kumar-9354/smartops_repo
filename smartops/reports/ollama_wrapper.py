# reports/ollama_wrapper.py
from langchain_core.language_models.llms import LLM
from typing import Optional, List, Any, Mapping
import ollama

class OllamaLLM(LLM):
    model: str = "qwen:0.5b"  # default model

    def __init__(self, model: str = "qwen:0.5b"):
        super().__init__()
        self.model = model

    @property
    def _llm_type(self) -> str:
        return "ollama"

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> str:
        """Call Ollama locally and return the response text."""
        try:
            response = ollama.chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}]
            )
            return response["message"]["content"]
        except Exception as e:
            return f"⚠️ Ollama error: {str(e)}"

    @property
    def _identifying_params(self) -> Mapping[str, Any]:
        return {"model": self.model}