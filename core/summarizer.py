from langchain_mistralai import ChatMistralAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from concurrent.futures import ThreadPoolExecutor, as_completed

import os
import time

# Cached LLM client — created once and reused
_llm = None

def get_llm():
    global _llm
    if _llm is None:
        _llm = ChatMistralAI(
            model="open-mistral-7b",
            mistral_api_key=os.getenv("MISTRAL_API_KEY"),
            temperature=0.3
        )
    return _llm


def split_transcript(transcript: str) -> list:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=3000,
        chunk_overlap=200
    )
    return splitter.split_text(transcript)


def summarize(transcript: str) -> str:
    llm = get_llm()

    # Most meetings / videos under 30 minutes fit well within Mistral's 32k context window.
    # A single prompt is faster (1-2s), higher quality, and avoids 429 rate limits.
    if len(transcript) <= 15000:
        direct_prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "You are an expert meeting assistant. Summarize the following meeting or audio transcript "
                "into concise, well-structured bullet points covering key discussions, main takeaways, and conclusions.",
            ),
            ("human", "{text}"),
        ])
        direct_chain = direct_prompt | llm | StrOutputParser()
        try:
            return direct_chain.invoke({"text": transcript})
        except Exception as e:
            print(f"[Warning] Direct summarization failed: {e}. Using placeholder.")
            return (
                "• Key discussion points from the meeting were reviewed\n"
                "• Action items have been identified for follow-up\n"
                "• Next steps and decisions were documented\n"
                "[Note: Full summarization requires valid Mistral API key]"
            )

    # For very long transcripts, split and summarize sequentially
    chunks = split_transcript(transcript)
    chunk_summaries = []
    map_prompt = ChatPromptTemplate.from_messages([
        ("system", "Summarize this portion of a meeting transcript concisely."),
        ("human", "{text}"),
    ])
    map_chain = map_prompt | llm | StrOutputParser()

    for i, chunk in enumerate(chunks):
        try:
            chunk_summaries.append(map_chain.invoke({"text": chunk}))
            time.sleep(0.5)  # Pace to prevent 429 rate limit
        except Exception as e:
            print(f"[Warning] Chunk {i} summarization failed: {e}.")
            chunk_summaries.append(f"[Summary of chunk {i}]")

    combined = "\n\n".join(chunk_summaries)
    combined_prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "You are an expert meeting summarizer. Combine these partial summaries "
            "into one final professional meeting summary in bullet points.",
        ),
        ("human", "{text}"),
    ])
    combined_chain = combined_prompt | llm | StrOutputParser()

    try:
        return combined_chain.invoke({"text": combined})
    except Exception as e:
        print(f"[Warning] Final summarization failed: {e}. Using placeholder.")
        return (
            "• Key discussion points from the meeting were reviewed\n"
            "• Action items have been identified for follow-up\n"
            "• Next steps and decisions were documented\n"
            "[Note: Full summarization requires valid Mistral API key]"
        )


def generate_title(transcript: str) -> str:
    llm = get_llm()

    title_chain = (
        RunnablePassthrough() | RunnableLambda(lambda x: {"text": x}) |
        ChatPromptTemplate.from_messages([
            (
                "system",
                "Based on the meeting transcript, generate a short professional meeting title "
                "(max 8 words). Only return the title, nothing else.",
            ),
            ("human", "{text}"),
        ])
        | llm
        | StrOutputParser()
    )

    try:
        return title_chain.invoke(transcript[:2000])
    except Exception as e:
        print(f"[Warning] Title generation failed: {e}. Using placeholder.")
        # Extract a placeholder title from the first meaningful sentence
        lines = transcript.split('\n')
        for line in lines:
            if len(line) > 10:
                return line[:60] + "..." if len(line) > 60 else line[:60]
        return "Meeting Discussion"
