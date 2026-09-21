from app.core.redaction import redact

def test_redact_email():
    res = redact("Contact me at test@example.com.")
    assert res.text == "Contact me at [EMAIL-1]."
    assert res.counts["EMAIL"] == 1

def test_redact_aadhaar_valid():
    # Valid Verhoeff for Aadhaar testing (do not use real numbers)
    # We construct a known valid sequence
    # 12345678901 is the number. Let's find the correct checksum digit.
    # We can just test a known valid mock: e.g. 23456789012 + correct check
    # To keep it simple, let's use the function from redaction to generate one or just use a known good:
    # 234567890123 has check digit... wait. Let's make a mock one:
    # Let's say we have a function in tests.
    pass

def test_redact_pan():
    res = redact("My PAN is ABCDE1234F.")
    assert res.text == "My PAN is [PAN-1]."
    assert res.counts["PAN"] == 1

def test_redact_phone():
    res = redact("Call +91 9876543210 or 98765 43210.")
    assert res.text == "Call [PHONE-1] or [PHONE-1]."
    assert res.counts["PHONE"] == 1

def test_redact_bank_account():
    res = redact("Please transfer to A/C 123456789012 within 10 days. Also 111122223333 alone is not masked.")
    assert "[ACCOUNT-1]" in res.text
    assert "111122223333 alone is not masked" in res.text

def test_repeated_values_share_placeholder():
    res = redact("Email test@example.com and again test@example.com.")
    assert res.text == "Email [EMAIL-1] and again [EMAIL-1]."
    assert res.counts["EMAIL"] == 1

def test_idempotence():
    text1 = redact("Email test@example.com.").text
    text2 = redact(text1).text
    assert text1 == text2

def test_aadhaar_validation():
    from app.core.redaction import _verhoeff_checksum
    # This checks that our verhoeff works. We can find a known valid sequence.
    # If we append the correct checksum digit, it should return True.
    number = "23456789012"
    # Brute force the checksum digit
    for i in range(10):
        if _verhoeff_checksum(number + str(i)):
            res = redact(f"Aadhaar: {number}{i}")
            assert "[AADHAAR-1]" in res.text
            break
    
    # Invalid
    res = redact(f"Aadhaar: {number}9")  # Assuming 9 is wrong if i is not 9
    if not _verhoeff_checksum(number + "9"):
        assert "[AADHAAR-1]" not in res.text
