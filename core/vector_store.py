"""
vector_store.py — Vector database management using ChromaDB and Mistral / HuggingFace embeddings.
Optimized for ultra-fast cloud deployment (Render, AWS, GCP) with zero RAM bloat.
"""

import os
import re
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

CHROMA_DIR = "vector_db"
DEFAULT_COLLECTION = "aurix_documents"
LOCAL_EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# Global cached embeddings instance
_embeddings = None


def get_embeddings():
    """
    Returns an embedding model.
    Prioritizes Mistral cloud embeddings (mistral-embed) for ultra-fast indexing
    and near-zero RAM usage on cloud hosts like Render. Falls back to local HuggingFace.
    """
    global _embeddings
    if _embeddings is None:
        mistral_key = os.getenv("MISTRAL_API_KEY", "").strip()
        if mistral_key:
            try:
                from langchain_mistralai import MistralAIEmbeddings
                print("[VectorStore] Using cloud embeddings: MistralAIEmbeddings (mistral-embed, 1024-dim)")
                _embeddings = MistralAIEmbeddings(api_key=mistral_key, model="mistral-embed")
                return _embeddings
            except Exception as e:
                print(f"[VectorStore Warning] Cloud embeddings failed ({e}), falling back to local.")

        try:
            from langchain_huggingface import HuggingFaceEmbeddings
        except ImportError:
            from langchain_community.embeddings import HuggingFaceEmbeddings

        print(f"[VectorStore] Loading local embeddings model: {LOCAL_EMBEDDING_MODEL}")
        _embeddings = HuggingFaceEmbeddings(
            model_name=LOCAL_EMBEDDING_MODEL,
            model_kwargs={"device": "cpu"}
        )

    return _embeddings


def sanitize_collection_name(name: str) -> str:
    """Ensure collection name meets Chroma requirements: 3-63 chars, alphanumeric, _ or -."""
    clean = re.sub(r"[^a-zA-Z0-9_-]", "_", name)
    clean = clean.strip("_-")
    if len(clean) < 3:
        clean = "col_" + clean
    return clean[:63]


def build_vector_store(text: str, session_id: str = None) -> Chroma:
    """
    Builds a vector store from document or transcript text.
    Uses session-specific collection names to isolate documents across sessions.
    """
    if not text or not text.strip():
        raise ValueError("Cannot build vector store from empty text.")

    col_name = sanitize_collection_name(f"doc_{session_id}" if session_id else DEFAULT_COLLECTION)
    print(f"[VectorStore] Indexing content into collection '{col_name}'...")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150,
        separators=["\n\n--- Page", "\n\n", "\n", ". ", " "]
    )
    chunks = splitter.split_text(text)

    docs = [
        Document(
            page_content=chunk,
            metadata={"chunk_index": i, "session_id": session_id or "default"}
        )
        for i, chunk in enumerate(chunks)
    ]

    embeddings = get_embeddings()

    # Clear old collection if it exists for this session
    try:
        import chromadb
        client = chromadb.PersistentClient(path=CHROMA_DIR)
        try:
            client.delete_collection(name=col_name)
        except Exception:
            pass
    except Exception:
        pass

    vector_store = Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
        collection_name=col_name,
        persist_directory=CHROMA_DIR
    )

    print(f"[VectorStore] Successfully indexed {len(docs)} chunks in collection '{col_name}'.")
    return vector_store


def load_vector_store(session_id: str = None) -> Chroma:
    """Load existing vector store collection."""
    col_name = sanitize_collection_name(f"doc_{session_id}" if session_id else DEFAULT_COLLECTION)
    embeddings = get_embeddings()
    return Chroma(
        collection_name=col_name,
        embedding_function=embeddings,
        persist_directory=CHROMA_DIR
    )


def get_retriever(vector_store: Chroma, k: int = 6):
    """Returns a similarity retriever configured to return top k chunks."""
    return vector_store.as_retriever(
        search_type="similarity",
        search_kwargs={"k": k}
    )
