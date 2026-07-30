"""Unit tests for overview intent detection and section slicing."""

from app.services.llm import extract_section_text, is_overview_question, is_section_summarize_question


def test_overview_detection_positive():
    assert is_overview_question("Summarize this document")
    assert is_overview_question("What are the key points?")
    assert is_overview_question("Give me an overview")
    assert is_overview_question("TLDR please")
    assert is_overview_question("summarize this doc in detail")


def test_overview_detection_negative():
    assert not is_overview_question("What is the refund policy?")
    assert not is_overview_question("List all important dates mentioned")
    assert not is_overview_question("Who signed the contract?")
    assert not is_overview_question("summarize module 1")


def test_section_summarize_detection():
    assert is_section_summarize_question("summarize module 1")
    assert is_section_summarize_question("Summarize Chapter 2 in detail")
    assert not is_section_summarize_question("summarize this document")


def test_extract_section_text():
    text = """TOC here

MODULE 1 — Scaling Laws

Content about scaling laws and MoE.

MODULE 2 — Agents

Content about agents.
"""
    section = extract_section_text(text, "summarize module 1")
    assert section is not None
    assert "Scaling Laws" in section
    assert "MODULE 2" not in section
    assert "agents" not in section.lower() or "Agents" not in section.split("MODULE 2")[0]
