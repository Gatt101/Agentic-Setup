from __future__ import annotations

import os
from functools import lru_cache

from langchain_openai import ChatOpenAI

from core.config import settings


def _configure_langsmith_environment() -> None:
    os.environ["LANGCHAIN_TRACING_V2"] = "true" if settings.langchain_tracing_v2 else "false"
    if settings.langchain_api_key:
        os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key
    if settings.langchain_project:
        os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project
    if settings.langchain_endpoint:
        os.environ["LANGCHAIN_ENDPOINT"] = settings.langchain_endpoint


def _assert_openai_key() -> None:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required to run LangGraph agents.")


@lru_cache(maxsize=1)
def get_supervisor_llm() -> ChatOpenAI:
    _configure_langsmith_environment()
    _assert_openai_key()
    return ChatOpenAI(
        model=settings.supervisor_llm,
        temperature=0.1,
        api_key=settings.openai_api_key,
    )


@lru_cache(maxsize=1)
def get_fast_llm() -> ChatOpenAI:
    _configure_langsmith_environment()
    _assert_openai_key()
    return ChatOpenAI(
        model=settings.fast_llm,
        temperature=0.0,
        api_key=settings.openai_api_key,
    )
