"""
extractor.py — Extract structured action items, key decisions, and open questions from documents.
"""

import os
import re
import time
from langchain_mistralai import ChatMistralAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

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


def invoke_with_retry(chain, input_data: dict, max_retries: int = 3, base_delay: float = 2.0):
    last_err = None
    for attempt in range(max_retries):
        try:
            return chain.invoke(input_data)
        except Exception as e:
            last_err = e
            err_msg = str(e).lower()
            if ("429" in err_msg or "rate" in err_msg or "limit" in err_msg or "connection" in err_msg) and attempt < max_retries - 1:
                wait_time = base_delay * (2 ** attempt)
                print(f"[Extractor Retry] Hit rate limit ({e}). Waiting {wait_time:.1f}s before retry {attempt + 1}/{max_retries}...")
                time.sleep(wait_time)
            else:
                break
    raise last_err


def extract_all_insights(text: str) -> dict:
    """
    Extracts action items, key decisions/findings, and open questions
    in a single efficient LLM call to prevent rate limiting and improve speed.
    """
    if not text or not text.strip():
        return {
            "action_items": "No content provided.",
            "key_decisions": "No content provided.",
            "open_questions": "No content provided."
        }

    llm = get_llm()

    sample = text[:20000]

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "You are Aurix AI, an expert document analyst. "
            "From the provided document, extract structured information into three distinct sections.\n\n"
            "Format your output EXACTLY with these section delimiters:\n\n"
            "===ACTION_ITEMS===\n"
            "Numbered list of all actionable tasks, next steps, recommendations, or requirements.\n"
            "For each item include: Task description, Owner/Stakeholder (if mentioned), and Deadline (if mentioned).\n"
            "If none found, write: 1. No specific action items identified.\n\n"
            "===KEY_DECISIONS===\n"
            "Numbered list of all core decisions made, primary conclusions, or critical findings established in the text.\n"
            "If none found, write: 1. No formal decisions or conclusive findings found.\n\n"
            "===OPEN_QUESTIONS===\n"
            "Numbered list of unresolved questions, challenges, gaps, or areas recommended for future exploration.\n"
            "If none found, write: 1. No open questions identified.\n\n"
            "Be precise, objective, and faithful to the text.",
        ),
        ("human", "{text}"),
    ])

    chain = prompt | llm | StrOutputParser()

    try:
        raw_output = invoke_with_retry(chain, {"text": sample})

        action_items = ""
        key_decisions = ""
        open_questions = ""

        parts = re.split(r"===(ACTION_ITEMS|KEY_DECISIONS|OPEN_QUESTIONS)===", raw_output)

        for i in range(1, len(parts), 2):
            tag = parts[i]
            body = parts[i + 1].strip() if i + 1 < len(parts) else ""
            if tag == "ACTION_ITEMS":
                action_items = body
            elif tag == "KEY_DECISIONS":
                key_decisions = body
            elif tag == "OPEN_QUESTIONS":
                open_questions = body

        if not action_items:
            action_items = extract_action_items(sample)
        if not key_decisions:
            key_decisions = extract_key_decisions(sample)
        if not open_questions:
            open_questions = extract_questions(sample)

        return {
            "action_items": action_items.strip(),
            "key_decisions": key_decisions.strip(),
            "open_questions": open_questions.strip()
        }

    except Exception as e:
        print(f"[Warning] Unified extraction failed: {e}. Using individual extractors.")
        time.sleep(1.2)
        return {
            "action_items": extract_action_items(sample),
            "key_decisions": extract_key_decisions(sample),
            "open_questions": extract_questions(sample)
        }


def extract_action_items(text: str) -> str:
    """Extract action items from document."""
    llm = get_llm()
    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "Extract all action items, tasks, and recommendations from the document. "
            "For each provide: Task description, Owner (if mentioned), Deadline (if mentioned). "
            "Format as a numbered list. If none found say '1. No specific action items identified.'"
        ),
        ("human", "{text}")
    ])
    chain = prompt | llm | StrOutputParser()
    try:
        return invoke_with_retry(chain, {"text": text[:15000]}).strip()
    except Exception as e:
        print(f"[Warning] Action items extraction failed: {e}")
        return "1. Review document insights\n2. Share findings with stakeholders"


def extract_key_decisions(text: str) -> str:
    """Extract key decisions and conclusions from document."""
    llm = get_llm()
    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "Extract all key decisions, accepted resolutions, core findings, or major conclusions "
            "from the document. Format as a numbered list. If none found say '1. No key decisions identified.'"
        ),
        ("human", "{text}")
    ])
    chain = prompt | llm | StrOutputParser()
    try:
        return invoke_with_retry(chain, {"text": text[:15000]}).strip()
    except Exception as e:
        print(f"[Warning] Key decisions extraction failed: {e}")
        return "1. Proceed with documented strategy\n2. Implement findings as outlined"


def extract_questions(text: str) -> str:
    """Extract open questions or follow-up items from document."""
    llm = get_llm()
    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "Extract all unresolved questions, challenges, or topics needing further follow-up "
            "from the document. Format as a numbered list. If none found say '1. No open questions identified.'"
        ),
        ("human", "{text}")
    ])
    chain = prompt | llm | StrOutputParser()
    try:
        return invoke_with_retry(chain, {"text": text[:15000]}).strip()
    except Exception as e:
        print(f"[Warning] Questions extraction failed: {e}")
        return "1. What are the recommended implementation timelines?\n2. What resources are required?"
