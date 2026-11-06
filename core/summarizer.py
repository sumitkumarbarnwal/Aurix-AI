"""
summarizer.py — Document summarization and title generation with Mistral AI.
"""

import os
import re
import time
from langchain_mistralai import ChatMistralAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Cached LLM client
_llm = None


def get_llm():
    global _llm
    if _llm is None:
        api_key = os.getenv("MISTRAL_API_KEY", "").strip()
        _llm = ChatMistralAI(
            model="open-mistral-7b",
            mistral_api_key=api_key,
            temperature=0.3,
            max_retries=3,
        )
    return _llm


def invoke_with_retry(chain, input_data: dict, max_retries: int = 3, base_delay: float = 2.0):
    """Invokes a LangChain chain with exponential backoff on rate limits."""
    last_err = None
    for attempt in range(max_retries):
        try:
            return chain.invoke(input_data)
        except Exception as e:
            last_err = e
            err_msg = str(e).lower()
            if ("429" in err_msg or "rate" in err_msg or "limit" in err_msg or "connection" in err_msg) and attempt < max_retries - 1:
                wait_time = base_delay * (2 ** attempt)
                print(f"[Summarizer Retry] Hit rate limit ({e}). Waiting {wait_time:.1f}s before retry {attempt + 1}/{max_retries}...")
                time.sleep(wait_time)
            else:
                break
    raise last_err


def split_document(text: str, chunk_size: int = 8000, chunk_overlap: int = 400) -> list:
    """Split long documents into manageable chunks."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n--- Page", "\n\n", "\n", ". ", " "]
    )
    return splitter.split_text(text)


def summarize(text: str) -> str:
    """
    Generate a comprehensive, structured summary of the document.
    """
    if not text or not text.strip():
        return "No text provided for summarization."

    llm = get_llm()

    # If within context limit (<= 25,000 characters ~ 5,000 words), direct single-call summary
    if len(text) <= 25000:
        direct_prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "You are Aurix AI, an elite document intelligence and research analyst. "
                "Analyze the following document and generate a thorough, clear, and well-structured summary.\n\n"
                "Format your summary with clean bullet points covering:\n"
                "• Executive Overview (core objective, thesis, or context)\n"
                "• Major Topics & Discussion Points (key arguments, methodologies, data, or facts)\n"
                "• Key Conclusions & Takeaways (primary outcomes, implications, or recommendations)\n\n"
                "Ensure every point is factual, insightful, and strictly based on the text.",
            ),
            ("human", "{text}"),
        ])
        direct_chain = direct_prompt | llm | StrOutputParser()

        try:
            summary = invoke_with_retry(direct_chain, {"text": text})
            return summary.strip()
        except Exception as e:
            print(f"[Warning] Direct summarization failed: {e}. Falling back to rule-based summary.")
            return _fallback_summary(text)

    # For very large documents (> 25k chars), use map-reduce with safe pacing
    chunks = split_document(text, chunk_size=8000, chunk_overlap=400)
    chunk_summaries = []

    map_prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "You are Aurix AI. Summarize this section of a larger document concisely, "
            "capturing key facts, numbers, discussions, and decisions in bullet points.",
        ),
        ("human", "{text}"),
    ])
    map_chain = map_prompt | llm | StrOutputParser()

    for i, chunk in enumerate(chunks):
        try:
            res = invoke_with_retry(map_chain, {"text": chunk})
            chunk_summaries.append(res)
            time.sleep(1.2)  # Respect Mistral free tier 1 req/sec limit
        except Exception as e:
            print(f"[Warning] Chunk {i + 1}/{len(chunks)} summarization failed: {e}")
            chunk_summaries.append(f"Section {i + 1}: Overview of key discussions.")

    combined = "\n\n".join(chunk_summaries)
    combine_prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "You are Aurix AI, an elite document intelligence analyst. "
            "Synthesize the following partial summaries into one final, polished, and structured document summary.\n\n"
            "Include:\n"
            "• Executive Overview\n"
            "• Key Findings & Major Discussion Points\n"
            "• Final Conclusions & Takeaways\n\n"
            "Format cleanly with bullet points.",
        ),
        ("human", "{text}"),
    ])
    combine_chain = combine_prompt | llm | StrOutputParser()

    try:
        time.sleep(1.2)
        summary = invoke_with_retry(combine_chain, {"text": combined})
        return summary.strip()
    except Exception as e:
        print(f"[Warning] Final combine summarization failed: {e}. Returning combined section summaries.")
        return combined


def generate_title(text: str) -> str:
    """
    Generate a concise, professional title (under 8 words) for the document.
    """
    if not text or not text.strip():
        return "Document Analysis"

    llm = get_llm()

    title_prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "Based on the document text, generate a short, professional title (max 8 words) "
            "that accurately describes the subject. Return ONLY the title text, nothing else. "
            "Do not include quotes or prefixes.",
        ),
        ("human", "{text}"),
    ])
    title_chain = title_prompt | llm | StrOutputParser()

    # Use first 3,000 characters
    sample = text[:3000]

    try:
        title = invoke_with_retry(title_chain, {"text": sample})
        title = title.strip().strip('"').strip("'").strip("*").strip("#")
        # Remove any leading 'Title:' prefix
        title = re.sub(r"^Title:\s*", "", title, flags=re.IGNORECASE)
        if title:
            return title[:80]
    except Exception as e:
        print(f"[Warning] Title generation failed: {e}.")

    # Fallback title from first meaningful line
    for line in text.split("\n"):
        line = line.strip().lstrip("#").strip("-").strip()
        if len(line) > 8 and not line.startswith("--- Page"):
            clean = re.sub(r"[^\w\s-]", "", line)
            words = clean.split()
            if words:
                return " ".join(words[:8])

    return "Document Summary & Analysis"


def _fallback_summary(text: str) -> str:
    """Rule-based fallback summary when API is unreachable."""
    lines = [l.strip() for l in text.split("\n") if l.strip() and not l.startswith("--- Page")]
    key_points = []
    for l in lines[:6]:
        if len(l) > 20:
            key_points.append(f"• {l[:150]}...")
    if not key_points:
        key_points = [
            "• Document content successfully extracted and indexed.",
            "• Content is ready for interactive Q&A in the chat section below."
        ]
    return (
        "• Document overview and key discussion points extracted:\n" +
        "\n".join(key_points) +
        "\n\n[Note: Configure a valid MISTRAL_API_KEY in .env for full AI summarization]"
    )
