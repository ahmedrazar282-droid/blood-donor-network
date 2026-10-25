"""Unit tests for the blood compatibility and eligibility rules."""
from datetime import date, timedelta
from types import SimpleNamespace as NS

import pytest

from app.services import BLOOD_TYPES, can_donate, days_until_eligible, is_eligible, validate_request_form


def test_o_negative_is_universal_donor():
    assert all(can_donate("O-", t) for t in BLOOD_TYPES)


def test_ab_positive_is_universal_recipient():
    assert all(can_donate(t, "AB+") for t in BLOOD_TYPES)


@pytest.mark.parametrize("donor, recipients", [
    ("O+", {"O+", "A+", "B+", "AB+"}),
    ("A-", {"A-", "A+", "AB-", "AB+"}),
    ("A+", {"A+", "AB+"}),
    ("B-", {"B-", "B+", "AB-", "AB+"}),
    ("B+", {"B+", "AB+"}),
    ("AB-", {"AB-", "AB+"}),
    ("AB+", {"AB+"}),
])
def test_compatibility_table(donor, recipients):
    assert {t for t in BLOOD_TYPES if can_donate(donor, t)} == recipients


def test_positive_never_gives_to_negative():
    for d in BLOOD_TYPES:
        for t in BLOOD_TYPES:
            if d.endswith("+") and t.endswith("-"):
                assert not can_donate(d, t)


def _donor(days_ago=None, available=True):
    last = date.today() - timedelta(days=days_ago) if days_ago is not None else None
    return NS(is_available=available, last_donation_date=last)


def test_never_donated_is_eligible():
    assert is_eligible(_donor())


def test_60_days_ago_not_eligible():
    assert not is_eligible(_donor(60))
    assert days_until_eligible(_donor(60)) == 30


def test_exactly_90_days_is_eligible():
    assert is_eligible(_donor(90))


def test_100_days_ago_eligible():
    assert is_eligible(_donor(100))


def test_unavailable_not_eligible():
    assert not is_eligible(_donor(200, available=False))


def test_request_validation():
    good = {"patient_name": "Ali", "hospital": "Civil Hospital", "blood_type": "O+", "city": "Sukkur",
            "urgency": "High", "contact_phone": "0300-1234567", "units": "2"}
    assert validate_request_form(good) == []
    assert validate_request_form({**good, "city": "Lahore"})
    assert validate_request_form({**good, "blood_type": "X+"})
    assert validate_request_form({**good, "contact_phone": "12345"})
    assert validate_request_form({**good, "units": "0"})
