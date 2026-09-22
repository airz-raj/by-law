from app.core.evidence import locate
from app.core.models import ReceiptReason


def test_exact_match():
    source = "The tenant shall vacate the premises."
    quote = "vacate the premises"
    receipt = locate(quote, source)
    assert receipt.found is True
    assert source[receipt.start : receipt.end] == quote


def test_normalised_match():
    source = "The tenant shall\n  vacate   the premises."
    quote = "vacate the premises"
    receipt = locate(quote, source)
    assert receipt.found is True
    assert source[receipt.start : receipt.end] == "vacate   the premises"


def test_curly_quotes_and_dashes():
    source = "He said \u201cpay \u2014 now\u201d."
    quote = 'He said "pay - now".'
    receipt = locate(quote, source)
    assert receipt.found is True
    assert source[receipt.start : receipt.end] == source


def test_ellipsis():
    source = "Pay Rs 50000 within 15 days or face legal action."
    quote = "Pay Rs 50000 ... or face legal action."
    receipt = locate(quote, source)
    assert receipt.found is True
    assert (
        source[receipt.start : receipt.end] == "Pay Rs 50000 within 15 days or face legal action."
    )


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


def test_a_quote_shorter_than_twelve_characters_is_not_confirmed():
    from app.core.evidence import locate
    from app.core.models import ReceiptReason

    receipt = locate("too short", "The document says too short somewhere in it.")
    assert receipt.found is False
    assert receipt.reason is ReceiptReason.TOO_SHORT


def test_a_quote_whose_characters_were_dropped_in_normalising_still_resolves():
    """Soft hyphens and zero-width marks fold away, so offsets must survive them."""
    from app.core.evidence import locate

    source = "The tenant shall­vacate the premises within seven days of receipt."
    receipt = locate("vacate the premises within seven days", source)
    assert receipt.found is True
    assert receipt.start is not None
    assert "vacate" in source[receipt.start : receipt.end]


def test_offsets_slice_back_to_the_matched_text_across_line_breaks():
    from app.core.evidence import locate

    source = "You are called upon to\nvacate the tenanted premises\nwithin seven days."
    receipt = locate("vacate the tenanted premises within seven days", source)
    assert receipt.found is True
    sliced = source[receipt.start : receipt.end]
    assert "vacate" in sliced
    assert "seven days" in sliced
