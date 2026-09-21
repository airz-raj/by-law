from datetime import date
from app.core.dates import find_dates

def test_find_dates_numeric():
    # DD/MM/YYYY
    res = find_dates("Received on 15/08/2026.")
    assert len(res) == 1
    assert res[0].value == date(2026, 8, 15)
    assert res[0].raw == "15/08/2026"

    # DD-MM-YYYY
    res = find_dates("15-08-2026")
    assert res[0].value == date(2026, 8, 15)

    # DD.MM.YYYY
    res = find_dates("15.08.2026")
    assert res[0].value == date(2026, 8, 15)

def test_find_dates_dmy():
    # D Month YYYY
    res = find_dates("15 August 2026")
    assert res[0].value == date(2026, 8, 15)

    # Dth Month, YYYY
    res = find_dates("15th August, 2026")
    assert res[0].value == date(2026, 8, 15)

    # Ordinal suffixes
    for suffix in ["1st", "2nd", "3rd", "21st", "24th"]:
        res = find_dates(f"{suffix} January 2026")
        assert len(res) == 1
        assert res[0].value.month == 1

def test_find_dates_mdy():
    # Month D, YYYY
    res = find_dates("August 15, 2026")
    assert res[0].value == date(2026, 8, 15)

    # Month Dth, YYYY
    res = find_dates("August 15th, 2026")
    assert res[0].value == date(2026, 8, 15)

def test_find_dates_invalid_skipped():
    res = find_dates("Date: 31/02/2026.")
    assert len(res) == 0

def test_find_dates_two_digit_years_ignored():
    res = find_dates("15/08/26")
    assert len(res) == 0

def test_multiple_dates_with_offsets():
    text = "Notice dated 12/07/2026 received on 15 July 2026."
    res = find_dates(text)
    assert len(res) == 2
    assert res[0].value == date(2026, 7, 12)
    assert res[1].value == date(2026, 7, 15)
    
    assert text[res[0].start:res[0].end] == "12/07/2026"
    assert text[res[1].start:res[1].end] == "15 July 2026"
