"""Tests for masking personal identifiers before text reaches the model.

Aadhaar numbers are generated here from an independent Verhoeff check-digit
implementation, so no number that could belong to a real person appears in
the repository.
"""

from __future__ import annotations

import pytest

from app.core.redaction import redact

_VERHOEFF_D = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 2, 3, 4, 0, 6, 7, 8, 9, 5),
    (2, 3, 4, 0, 1, 7, 8, 9, 5, 6),
    (3, 4, 0, 1, 2, 8, 9, 5, 6, 7),
    (4, 0, 1, 2, 3, 9, 5, 6, 7, 8),
    (5, 9, 8, 7, 6, 0, 4, 3, 2, 1),
    (6, 5, 9, 8, 7, 1, 0, 4, 3, 2),
    (7, 6, 5, 9, 8, 2, 1, 0, 4, 3),
    (8, 7, 6, 5, 9, 3, 2, 1, 0, 4),
    (9, 8, 7, 6, 5, 4, 3, 2, 1, 0),
)
_VERHOEFF_P = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 5, 7, 6, 2, 8, 3, 0, 9, 4),
    (5, 8, 0, 3, 7, 9, 6, 1, 4, 2),
    (8, 9, 1, 6, 0, 4, 3, 5, 2, 7),
    (9, 4, 5, 3, 1, 2, 6, 8, 7, 0),
    (4, 2, 8, 6, 5, 7, 3, 9, 0, 1),
    (2, 7, 9, 3, 8, 0, 6, 4, 1, 5),
    (7, 0, 4, 6, 9, 1, 3, 2, 5, 8),
)
_VERHOEFF_INV = (0, 4, 3, 2, 1, 5, 6, 7, 8, 9)


def with_check_digit(first_eleven: str) -> str:
    """Append the Verhoeff check digit, giving a well-formed 12-digit number."""
    checksum = 0
    for position, digit in enumerate(reversed(first_eleven)):
        checksum = _VERHOEFF_D[checksum][_VERHOEFF_P[(position + 1) % 8][int(digit)]]
    return first_eleven + str(_VERHOEFF_INV[checksum])


def break_check_digit(twelve_digits: str) -> str:
    """Return the same number with a deliberately wrong final digit."""
    wrong = (int(twelve_digits[-1]) + 1) % 10
    return twelve_digits[:-1] + str(wrong)


VALID_AADHAAR = with_check_digit("23456789012")
INVALID_AADHAAR = break_check_digit(VALID_AADHAAR)


def test_the_generator_and_breaker_disagree() -> None:
    assert VALID_AADHAAR != INVALID_AADHAAR
    assert len(VALID_AADHAAR) == 12


def test_email_is_masked() -> None:
    result = redact("Write to notices@example.invalid for a reply.")
    assert result.text == "Write to [EMAIL-1] for a reply."
    assert result.counts["EMAIL"] == 1


def test_a_checksum_valid_aadhaar_is_masked() -> None:
    result = redact(f"Aadhaar {VALID_AADHAAR} is on file.")
    assert result.text == "Aadhaar [AADHAAR-1] is on file."
    assert result.counts["AADHAAR"] == 1


@pytest.mark.parametrize("separator", [" ", "-"])
def test_a_grouped_aadhaar_is_masked(separator: str) -> None:
    grouped = separator.join((VALID_AADHAAR[0:4], VALID_AADHAAR[4:8], VALID_AADHAAR[8:12]))
    result = redact(f"Aadhaar {grouped} is on file.")
    assert "[AADHAAR-1]" in result.text
    assert grouped not in result.text


def test_a_checksum_invalid_number_is_left_alone() -> None:
    result = redact(f"Reference {INVALID_AADHAAR} in our records.")
    assert INVALID_AADHAAR in result.text
    assert "AADHAAR" not in result.counts


def test_pan_is_masked() -> None:
    result = redact("PAN ABCDE1234F belongs to the drawer.")
    assert result.text == "PAN [PAN-1] belongs to the drawer."
    assert result.counts["PAN"] == 1


@pytest.mark.parametrize("word", ["ABCD1234F", "ABCDE1234", "ABCDEF1234F", "ABCDE12345"])
def test_a_word_that_is_not_pan_shaped_is_left_alone(word: str) -> None:
    """Five letters, four digits, one letter. Anything else is not a PAN."""
    assert word in redact(f"Reference {word} in our file.").text


@pytest.mark.parametrize(
    "written",
    ["9876543210", "+91 9876543210", "+91-9876543210", "98765 43210", "98765-43210"],
)
def test_a_mobile_number_is_masked_however_it_is_written(written: str) -> None:
    result = redact(f"Call {written} before Friday.")
    assert "[PHONE-1]" in result.text
    assert result.counts["PHONE"] == 1


def test_a_number_starting_below_six_is_not_a_mobile_number() -> None:
    result = redact("Call 5876543210 before Friday.")
    assert "5876543210" in result.text
    assert "PHONE" not in result.counts


def test_an_account_number_near_a_keyword_is_masked() -> None:
    result = redact("Credit A/C 123456789012 within ten days.")
    assert "[ACCOUNT-1]" in result.text
    assert "123456789012" not in result.text


def test_a_bare_digit_run_is_not_treated_as_an_account_number() -> None:
    result = redact("Invoice total 111122223333 remains unpaid.")
    assert "111122223333" in result.text
    assert "ACCOUNT" not in result.counts


def test_the_same_value_always_gets_the_same_placeholder() -> None:
    result = redact("Write to a@example.invalid, or again to a@example.invalid.")
    assert result.text.count("[EMAIL-1]") == 2
    assert result.counts["EMAIL"] == 1


def test_two_different_values_get_different_placeholders() -> None:
    result = redact("Write to a@example.invalid or b@example.invalid.")
    assert "[EMAIL-1]" in result.text
    assert "[EMAIL-2]" in result.text
    assert result.counts["EMAIL"] == 2


def test_redacting_twice_changes_nothing_the_second_time() -> None:
    once = redact(
        f"PAN ABCDE1234F, Aadhaar {VALID_AADHAAR}, phone 9876543210, a@example.invalid"
    ).text
    assert redact(once).text == once


def test_names_and_addresses_are_not_masked() -> None:
    """The explanation has to say who is asking whom for what."""
    text = "Sunil Bharti of Sector 00, Example Nagar demands payment."
    assert redact(text).text == text


def test_counts_only_list_categories_that_were_found() -> None:
    result = redact("PAN ABCDE1234F and nothing else.")
    assert result.counts == {"PAN": 1}


# --- cases an audit of the finished build found leaking ---------------------


@pytest.mark.parametrize("written", ["ABCDE1234F", "abcde1234f", "Abcde1234f", "AbCdE1234f"])
def test_a_pan_is_masked_whatever_its_case(written: str) -> None:
    """PDF extraction and pasted text routinely change case."""
    result = redact(f"PAN {written} of the drawer.")
    assert written not in result.text
    assert "[PAN-1]" in result.text


def test_the_same_pan_in_two_cases_is_one_value() -> None:
    result = redact("PAN ABCDE1234F, also written abcde1234f.")
    assert result.counts["PAN"] == 1


@pytest.mark.parametrize("separator", [" ", "-", ".", "  "])
def test_an_aadhaar_is_masked_whatever_separates_its_groups(separator: str) -> None:
    grouped = separator.join((VALID_AADHAAR[0:4], VALID_AADHAAR[4:8], VALID_AADHAAR[8:12]))
    result = redact(f"Aadhaar {grouped} on file.")
    assert "[AADHAAR-1]" in result.text
    assert grouped not in result.text


@pytest.mark.parametrize(
    "written",
    [
        "9876543210",
        "98765 43210",
        "98765-43210",
        "98765.43210",
        "987-654-3210",
        "987 654 3210",
        "+91 9876543210",
        "+919876543210",
        "09876543210",
    ],
)
def test_a_mobile_number_is_masked_whatever_groups_it(written: str) -> None:
    result = redact(f"Reach me on {written} any day.")
    assert "[PHONE-1]" in result.text
    assert result.counts["PHONE"] == 1


def test_the_same_number_written_two_ways_is_one_value() -> None:
    result = redact("Call 9876543210 or 987-654-3210.")
    assert result.counts["PHONE"] == 1
    assert result.text.count("[PHONE-1]") == 2


@pytest.mark.parametrize(
    "text",
    [
        "Invoice total 111122223333 remains unpaid.",
        "PIN code 560001 for the address.",
        "Cheque number 004517 dated today.",
        "The sum of Rs. 48,500 is due.",
    ],
)
def test_ordinary_numbers_in_a_notice_are_left_alone(text: str) -> None:
    assert redact(text).text == text
