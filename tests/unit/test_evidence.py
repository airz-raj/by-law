from app.core.evidence import locate
from app.core.models import ReceiptReason

def test_exact_match():
    source = "The tenant shall vacate the premises."
    quote = "vacate the premises"
    receipt = locate(quote, source)
    assert receipt.found is True
    assert source[receipt.start:receipt.end] == quote

def test_normalised_match():
    source = "The tenant shall\n  vacate   the premises."
    quote = "vacate the premises"
    receipt = locate(quote, source)
    assert receipt.found is True
    assert source[receipt.start:receipt.end] == "vacate   the premises"

def test_curly_quotes_and_dashes():
    source = "He said \u201cpay \u2014 now\u201d."
    quote = 'He said "pay - now".'
    receipt = locate(quote, source)
    assert receipt.found is True
    assert source[receipt.start:receipt.end] == source

def test_ellipsis():
    source = "Pay Rs 50000 within 15 days or face legal action."
    quote = "Pay Rs 50000 ... or face legal action."
    receipt = locate(quote, source)
    assert receipt.found is True
    assert source[receipt.start:receipt.end] == "Pay Rs 50000 within 15 days or face legal action."

def test_ellipsis_out_of_order():
    source = "Pay Rs 50000 within 15 days or face legal action."
    quote = "face legal action ... Pay Rs 50000"
    receipt = locate(quote, source)
    assert receipt.found is False

def test_fabricated_quote():
    source = "Pay Rs 50000 within 15 days."
    quote = "Pay Rs 60000 within 15 days."
    receipt = locate(quote, source)
    assert receipt.found is False
    assert receipt.reason == ReceiptReason.NOT_FOUND

def test_too_short_quote():
    source = "Pay Rs 50000 within 15 days."
    quote = "Pay Rs 50"
    receipt = locate(quote, source)
    assert receipt.found is False
    assert receipt.reason == ReceiptReason.TOO_SHORT
