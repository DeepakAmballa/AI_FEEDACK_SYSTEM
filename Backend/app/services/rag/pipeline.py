"""
Local RAG Pipeline — SentenceTransformers + FAISS
Provides subject-specific retrieval without sending full DB to OpenAI.
"""
import os
import json
import pickle
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# Lazy-load heavy libraries to allow app startup even if not installed yet
_model = None
_faiss = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("SentenceTransformer model loaded: all-MiniLM-L6-v2")
    return _model


def _get_faiss():
    global _faiss
    if _faiss is None:
        import faiss
        _faiss = faiss
    return _faiss


def chunk_text(text: str, chunk_size: int = 400, overlap: int = 80) -> List[str]:
    """Split text into overlapping word-level chunks."""
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk = " ".join(words[start:end])
        if len(chunk.strip()) > 20:  # skip trivially short chunks
            chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


class SubjectRAGIndex:
    """In-memory FAISS index + metadata for one subject."""

    def __init__(self, subject_id: int, faiss_dir: str):
        self.subject_id = subject_id
        self.faiss_dir = faiss_dir
        self.index = None
        self.chunks: List[Dict] = []  # {text, source, doc_id, page_ref}

    def _index_path(self) -> Path:
        return Path(self.faiss_dir) / f"subject_{self.subject_id}.faiss"

    def _meta_path(self) -> Path:
        return Path(self.faiss_dir) / f"subject_{self.subject_id}_meta.pkl"

    def build_index(self, documents: List[Dict]) -> int:
        """
        Build FAISS index from a list of documents.
        Each document: {text, source_name, doc_id, doc_type}
        Returns: number of chunks indexed.
        """
        faiss = _get_faiss()
        model = _get_model()

        all_chunks = []
        for doc in documents:
            if not doc.get("text") or not doc["text"].strip():
                continue
            chunks = chunk_text(doc["text"])
            for chunk in chunks:
                all_chunks.append({
                    "text": chunk,
                    "source": doc.get("source_name", "unknown"),
                    "doc_id": doc.get("doc_id"),
                    "doc_type": doc.get("doc_type", "reference"),
                })

        if not all_chunks:
            logger.warning(f"No chunks to index for subject {self.subject_id}")
            return 0

        texts = [c["text"] for c in all_chunks]
        embeddings = model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
        embeddings = embeddings.astype(np.float32)

        dimension = embeddings.shape[1]
        index = faiss.IndexFlatIP(dimension)  # Inner product (cosine if normalized)
        faiss.normalize_L2(embeddings)
        index.add(embeddings)

        self.index = index
        self.chunks = all_chunks

        # Persist to disk
        Path(self.faiss_dir).mkdir(parents=True, exist_ok=True)
        faiss.write_index(index, str(self._index_path()))
        with open(self._meta_path(), "wb") as f:
            pickle.dump(all_chunks, f)

        logger.info(f"Built FAISS index for subject {self.subject_id}: {len(all_chunks)} chunks")
        return len(all_chunks)

    def load_index(self) -> bool:
        """Load persisted index from disk. Returns True if successful."""
        faiss = _get_faiss()
        try:
            if self._index_path().exists() and self._meta_path().exists():
                self.index = faiss.read_index(str(self._index_path()))
                with open(self._meta_path(), "rb") as f:
                    self.chunks = pickle.load(f)
                logger.info(f"Loaded FAISS index for subject {self.subject_id}: {len(self.chunks)} chunks")
                return True
        except Exception as e:
            logger.error(f"Failed to load FAISS index for subject {self.subject_id}: {e}")
        return False

    def retrieve(self, query: str, top_k: int = 5) -> List[Dict]:
        """Retrieve top-k most relevant chunks for the query."""
        if self.index is None or not self.chunks:
            if not self.load_index():
                return []

        faiss = _get_faiss()
        model = _get_model()

        query_embedding = model.encode([query], show_progress_bar=False, convert_to_numpy=True)
        query_embedding = query_embedding.astype(np.float32)
        faiss.normalize_L2(query_embedding)

        scores, indices = self.index.search(query_embedding, min(top_k, len(self.chunks)))
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx >= 0 and float(score) > 0.3:  # relevance threshold
                chunk = self.chunks[idx].copy()
                chunk["relevance_score"] = float(score)
                results.append(chunk)
        return results

    def delete_index(self):
        """Remove persisted index files."""
        self._index_path().unlink(missing_ok=True)
        self._meta_path().unlink(missing_ok=True)
        self.index = None
        self.chunks = []


# ─── Global index registry ────────────────────────────────────────────────────

_index_registry: Dict[int, SubjectRAGIndex] = {}


def get_subject_index(subject_id: int, faiss_dir: str) -> SubjectRAGIndex:
    if subject_id not in _index_registry:
        _index_registry[subject_id] = SubjectRAGIndex(subject_id, faiss_dir)
    return _index_registry[subject_id]


def build_subject_index(subject_id: int, documents: List[Dict], faiss_dir: str) -> int:
    idx = get_subject_index(subject_id, faiss_dir)
    return idx.build_index(documents)


def retrieve_for_subject(subject_id: int, query: str, top_k: int = 5, faiss_dir: str = "faiss_indexes") -> List[Dict]:
    idx = get_subject_index(subject_id, faiss_dir)
    return idx.retrieve(query, top_k=top_k)

