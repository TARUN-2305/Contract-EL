"""
groq_client.py — Legacy wrapper. Now delegates to llm_client.py.
Kept for backward compat with existing agent imports.
"""
from utils.llm_client import groq_chat, groq_json_extract, groq_narrate, get_groq_client, get_llm_client

__all__ = ["groq_chat", "groq_json_extract", "groq_narrate", "get_groq_client", "get_llm_client"]
