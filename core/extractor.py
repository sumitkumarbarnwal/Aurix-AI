from langchain_mistralai import ChatMistralAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from concurrent.futures import ThreadPoolExecutor
import os

# Cached LLM client — created once and reused
_llm = None

def get_llm():
    global _llm
    if _llm is None:
        _llm = ChatMistralAI(
            model="open-mistral-7b",
            mistral_api_key=os.getenv("MISTRAL_API_KEY"),
            temperature=0.2
        )
    return _llm


def build_chain(system_prompt: str):
    llm = get_llm()
    return (
        RunnablePassthrough() | RunnableLambda(lambda x: {"text": x}) | ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{text}"),
        ]) | llm | StrOutputParser()
    )


def extract_action_items(transcript: str) -> str:
    chain = build_chain(
        "You are an expert meeting analyst. From the meeting transcript, "
        "extract all action items. For each provide:\n"
        "- Task description\n"
        "- Owner (who is responsible)\n"
        "- Deadline (if mentioned, else write 'Not specified')\n\n"
        "Format as a numbered list. If none found say 'No action items found.'"
    )
    try:
        return chain.invoke(transcript)
    except Exception as e:
        print(f"[Warning] Action items extraction failed: {e}. Using placeholder.")
        return (
            "1. Follow up on discussion items - Owner: TBD - Deadline: Not specified\n"
            "2. Review meeting notes and share with team - Owner: TBD - Deadline: Not specified\n"
            "[Note: Full extraction requires valid Mistral API key]"
        )


def extract_key_decisions(transcript: str) -> str:
    chain = build_chain(
        "You are an expert meeting analyst. From the meeting transcript, "
        "extract all key decisions made. Format as a numbered list. "
        "If none found say 'No key decisions found.'"
    )
    try:
        return chain.invoke(transcript)
    except Exception as e:
        print(f"[Warning] Key decisions extraction failed: {e}. Using placeholder.")
        return (
            "1. Continue with planned approach\n"
            "2. Schedule follow-up meeting\n"
            "[Note: Full extraction requires valid Mistral API key]"
        )


def extract_questions(transcript: str) -> str:
    chain = build_chain(
        "From the meeting transcript, extract all unresolved questions "
        "or topics needing follow-up. Format as a numbered list. "
        "If none found say 'No open questions found.'"
    )
    try:
        return chain.invoke(transcript)
    except Exception as e:
        print(f"[Warning] Questions extraction failed: {e}. Using placeholder.")
        return (
            "1. What are the next steps?\n"
            "2. When will we reconvene to review progress?\n"
            "[Note: Full extraction requires valid Mistral API key]"
        )
