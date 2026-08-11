import numpy as np
from fastembed import TextEmbedding

MODEL_NAME = "intfloat/multilingual-e5-large"

_model: TextEmbedding | None = None


def get_model() -> TextEmbedding:
    global _model
    if _model is None:
        _model = TextEmbedding(model_name=MODEL_NAME)
    return _model


def embed_texts(texts: list[str]) -> np.ndarray:
    vectors = np.array(list(get_model().embed(texts)), dtype=np.float32)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.clip(norms, 1e-9, None)


def passage_text(heading_path: str, spoken: str) -> str:
    return f"passage: {heading_path}. {spoken}"


def query_text(question: str) -> str:
    return f"query: {question}"