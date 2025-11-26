import os
import threading
from typing import Optional

import vertexai
from vertexai.generative_models import GenerationConfig, GenerativeModel


class VertexAIClient:
    """Singleton helper to interact with Vertex AI Generative Models."""

    _instance: Optional["VertexAIClient"] = None
    _lock = threading.Lock()

    def __init__(self, *, project_id: str, location: str, model_name: str):
        vertexai.init(project=project_id, location=location)
        self._model_name = model_name
        self._model = GenerativeModel(model_name)

    @classmethod
    def from_env(cls) -> "VertexAIClient":
        with cls._lock:
            if cls._instance is None:
                project_id = os.getenv("VERTEX_PROJECT_ID")
                if not project_id:
                    raise ValueError("VERTEX_PROJECT_ID environment variable is required for Vertex AI usage.")
                location = os.getenv("VERTEX_LOCATION", "us-central1")
                model_name = os.getenv("VERTEX_MODEL", "gemini-2.5-flash")
                cls._instance = cls(project_id=project_id, location=location, model_name=model_name)
            return cls._instance

    def generate(
        self,
        prompt: str,
        *,
        temperature: float = 0.4,
        max_output_tokens: int = 2048,
    ) -> str:
        config = GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            top_p=0.95,
            top_k=40,
        )
        response = self._model.generate_content(
            [prompt],
            generation_config=config,
        )
        if hasattr(response, "text"):
            return response.text
        if hasattr(response, "candidates") and response.candidates:
            return response.candidates[0].content.parts[0].text
        raise ValueError("Vertex AI response did not contain any text.")

