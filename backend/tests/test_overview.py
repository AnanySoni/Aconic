"""Unit tests for overview intent detection."""

from app.services.llm import is_overview_question


def test_overview_detection_positive():
    assert is_overview_question("Summarize this document")
    assert is_overview_question("What are the key points?")
    assert is_overview_question("Give me an overview")
    assert is_overview_question("TLDR please")


def test_overview_detection_negative():
    assert not is_overview_question("What is the refund policy?")
    assert not is_overview_question("List all important dates mentioned")
    assert not is_overview_question("Who signed the contract?")
