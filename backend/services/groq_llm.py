from __future__ import annotations

import os
from functools import lru_cache

from langchain_groq import ChatGroq

from core.config import settings


def _configure_langsmith_environment() -> None:
    os.environ["LANGCHAIN_TRACING_V2"] = "true" if settings.langchain_tracing_v2 else "false"
    if settings.langchain_api_key:
        os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key
    if settings.langchain_project:
        os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project
    if settings.langchain_endpoint:
        os.environ["LANGCHAIN_ENDPOINT"] = settings.langchain_endpoint


def _assert_groq_key() -> None:
    if not settings.groq_api_key:
        raise RuntimeError("GROQ_API_KEY is required to run LangGraph agents.")


@lru_cache(maxsize=1)
def get_supervisor_llm() -> ChatGroq:
    _configure_langsmith_environment()
    _assert_groq_key()
    return ChatGroq(
        model=settings.supervisor_llm,
        temperature=0.1,
        api_key=settings.groq_api_key,
    )


@lru_cache(maxsize=1)
def get_fast_llm() -> ChatGroq:
    _configure_langsmith_environment()
    _assert_groq_key()
    return ChatGroq(
        model=settings.fast_llm,
        temperature=0.0,
        api_key=settings.groq_api_key,
    )
