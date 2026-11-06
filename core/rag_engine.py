"""
rag_engine.py — Retrieval-Augmented Generation (RAG) for document Q&A.
Enables users to ask questions about uploaded documents with grounded answers.
"""

import os
import time
from langchain_mistralai import ChatMistralAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from core.vector_store import build_vector_store, load_vector_store, get_retriever

# Cached LLM client
_llm = None


def get_llm():
    global _llm
    if _llm is None:
        _llm = ChatMistralAI(
            model="open-mistral-7b",
            mistral_api_key=os.getenv("MISTRAL_API_KEY", "").strip(),
            temperature=0.2,
            max_retries=3,
        )
    return _llm


def format_docs(docs):
    return "\n\n---\n\n".join([doc.page_content for doc in docs])


def build_rag_chain(text: str, session_id: str = None):
    """
    Builds a RAG chain for the provided document text and session.
    """
    vector_store = build_vector_store(text, session_id=session_id)
    retriever = get_retriever(vector_store, k=6)

    llm = get_llm()

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            """You are Aurix AI, an expert document intelligence assistant.
Your goal is to answer the user's question accurately, clearly, and informatively based ONLY on the provided document context below.

Rules:
1. Base your answer strictly on the facts, data, and statements present in the context.
2. If the document does not contain enough information to answer the question, state clearly:
   "Based on the uploaded document, I could not find information regarding this question."
3. When helpful, cite specific details, names, figures, page numbers, or sections from the context.
4. Keep your answer concise, direct, and well-structured using bullet points or bold text where appropriate.
5. Do NOT make up or assume facts not supported by the context.

Document Context:
{context}""",
        ),
        ("human", "{question}"),
    ])

    rag_chain = (
        {
            "context": retriever | RunnableLambda(format_docs),
            "question": RunnablePassthrough()
        }
        | prompt
        | llm
        | StrOutputParser()
    )

    return rag_chain


def ask_question(rag_chain, question: str) -> str:
    """
    Query the RAG chain with a user question and return the generated answer.
    """
    if not rag_chain:
        raise ValueError("RAG chain has not been initialized.")

    question = question.strip()
    if not question:
        return "Please provide a valid question."

    print(f"[RAG Engine] Processing Question: {question}")

    # Retry on rate limit with exponential backoff
    for attempt in range(3):
        try:
            answer = rag_chain.invoke(question)
            print(f"[RAG Engine] Answer generated ({len(answer)} chars)")
            return answer.strip()
        except Exception as e:
            err_msg = str(e).lower()
            if ("429" in err_msg or "rate" in err_msg or "limit" in err_msg) and attempt < 2:
                wait_time = 2.0 * (attempt + 1)
                print(f"[RAG Retry] Hit rate limit. Waiting {wait_time}s...")
                time.sleep(wait_time)
            else:
                print(f"[RAG Engine Error] {e}")
                raise e
