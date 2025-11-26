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
        max_output_tokens: int = 8192,  # Increased for longer responses
    ) -> str:
        config = GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            top_p=0.95,
            top_k=40,
        )
        try:
            response = self._model.generate_content(
                [prompt],
                generation_config=config,
            )
            if hasattr(response, "text"):
                return response.text
            if hasattr(response, "candidates") and response.candidates:
                return response.candidates[0].content.parts[0].text
            # Log the full response for debugging
            import sys
            print(f"DEBUG: Vertex AI response structure: {type(response)}", file=sys.stderr, flush=True)
            print(f"DEBUG: Response attributes: {dir(response)}", file=sys.stderr, flush=True)
            raise ValueError("Vertex AI response did not contain any text.")
        except Exception as e:
            import sys
            print(f"ERROR: Vertex AI generation failed: {type(e).__name__}: {str(e)}", file=sys.stderr, flush=True)
            raise

