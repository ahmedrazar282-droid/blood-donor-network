"""Integration tests: auth, roles, matching, privacy, expiry."""
from datetime import date, timedelta

import pytest

from app import create_app, db
from app.models import BloodRequest, Donor, RequestResponse, User, utcnow
from app.services import expire_old_requests, match_donors


@pytest.fixture()
def app(tmp_path):
    app = create_app({"TESTING": True, "WTF_CSRF_ENABLED": False,
                      "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'test.db'}"})
    yield app


def make_user(email, name="Test User", role="user", phone="0300-1111111", password="Password1"):
    u = User(full_name=name, email=email, phone=phone, role=role)
    u.set_password(password)
    db.session.add(u)
    db.session.commit()
    return u


def make_donor(user, blood, city="Sukkur", days_ago=None, available=True):
    last = date.today() - timedelta(days=days_ago) if days_ago is not None else None
    d = Donor(user_id=user.id, blood_type=blood, city=city, last_donation_date=last, is_available=available)
    db.session.add(d)
    db.session.commit()
    return d


def make_request(requester, blood="AB+", city="Sukkur", hours=24):
    r = BloodRequest(requester_id=requester.id, patient_name="Patient", blood_type=blood, units=1,
                     urgency="High", hospital="Civil Hospital", city=city, contact_phone="0301-2223334",
                     expires_at=utcnow() + timedelta(hours=hours))
    db.session.add(r)
    db.session.commit()
    return r


def login(client, email, password="Password1"):
    return client.post("/login", data={"email": email, "password": password}, follow_redirects=True)


def test_signup_hashes_password_and_rejects_duplicates(app):
    c = app.test_client()
    data = {"full_name": "Ahmed", "email": "a@x.com", "phone": "0300-1234567",
            "password": "Password1", "confirm": "Password1"}
    c.post("/signup", data=data)
    with app.app_context():
        u = User.query.filter_by(email="a@x.com").one()
        assert u.password_hash != "Password1" and "Password1" not in u.password_hash
        assert u.check_password("Password1")
    c.post("/logout")
    r = c.post("/signup", data=data, follow_redirects=True)
    assert b"already exists" in r.data
    with app.app_context():
        assert User.query.count() == 1


def test_wrong_password_rejected(app):
    with app.app_context():
        make_user("a@x.com")
    r = login(app.test_client(), "a@x.com", "wrong")
    assert b"Wrong email or password" in r.data


def test_normal_user_cannot_open_admin(app):
    with app.app_context():
        make_user("a@x.com")
        make_user("admin@x.com", role="admin")
    c = app.test_client()
    login(c, "a@x.com")
    assert c.get("/admin/").status_code == 403
    c2 = app.test_client()
    login(c2, "admin@x.com")
    assert c2.get("/admin/").status_code == 200


def test_blocked_user_cannot_login(app):
    with app.app_context():
        u = make_user("a@x.com")
        u.is_blocked = True
        db.session.commit()
    r = login(app.test_client(), "a@x.com")
    assert b"blocked" in r.data


def test_matching_uses_compatibility_eligibility_and_city(app):
    with app.app_context():
        req_user = make_user("r@x.com")
        r = make_request(req_user, blood="AB+")
        o_neg = make_donor(make_user("d1@x.com"), "O-", "Larkana", 200)
        same_city = make_donor(make_user("d2@x.com"), "A+", "Sukkur", 150)
        recent = make_donor(make_user("d3@x.com"), "O+", "Sukkur", 30)       # donated 30 days ago
        away = make_donor(make_user("d4@x.com"), "B+", "Sukkur", 200, available=False)
        ids = [d.id for d in match_donors(r)]
        assert ids == [same_city.id, o_neg.id]          # same city first
        assert recent.id not in ids and away.id not in ids

        r_o_neg = make_request(req_user, blood="O-")
        assert [d.id for d in match_donors(r_o_neg)] == [o_neg.id]   # only O- can give to O-


def test_requester_is_not_matched_with_self(app):
    with app.app_context():
        u = make_user("r@x.com")
        make_donor(u, "O+", "Sukkur", 200)
        assert match_donors(make_request(u, blood="O+")) == []


def test_donor_phone_hidden_until_accept(app):
    with app.app_context():
        req_user = make_user("r@x.com")
        donor_user = make_user("d@x.com", name="Donor Dan", phone="0345-9998887")
        donor = make_donor(donor_user, "O+", "Sukkur", 200)
        r = make_request(req_user, blood="O+")
        rid, did = r.id, donor.id
    c = app.test_client()
    login(c, "r@x.com")
    assert b"0345-9998887" not in c.get(f"/requests/{rid}").data
    c.post(f"/requests/{rid}/send/{did}")
    assert b"0345-9998887" not in c.get(f"/requests/{rid}").data      # pending
    dc = app.test_client()
    login(dc, "d@x.com")
    with app.app_context():
        resp_id = RequestResponse.query.one().id
    dc.post(f"/responses/{resp_id}/accept")
    assert b"0345-9998887" in c.get(f"/requests/{rid}").data          # accepted


def test_only_owner_can_fulfil_and_status_changes(app):
    with app.app_context():
        make_user("r@x.com")
        make_user("o@x.com")
        r = make_request(User.query.filter_by(email="r@x.com").one())
        rid = r.id
    other = app.test_client()
    login(other, "o@x.com")
    assert other.post(f"/requests/{rid}/fulfil").status_code == 403
    owner = app.test_client()
    login(owner, "r@x.com")
    owner.post(f"/requests/{rid}/fulfil")
    with app.app_context():
        assert db.session.get(BloodRequest, rid).status == "fulfilled"


def test_old_requests_expire(app):
    with app.app_context():
        u = make_user("r@x.com")
        old = make_request(u, hours=-1)
        fresh = make_request(u, hours=24)
        expire_old_requests()
        assert db.session.get(BloodRequest, old.id).status == "expired"
        assert db.session.get(BloodRequest, fresh.id).status == "pending"


def test_post_request_validation_and_rate_limit(app):
    with app.app_context():
        make_user("r@x.com")
    c = app.test_client()
    login(c, "r@x.com")
    bad = c.post("/requests/new", data={"patient_name": "A", "city": "Lahore"}, follow_redirects=True)
    assert b"valid" in bad.data
    good = {"patient_name": "Ali Hassan", "blood_type": "B+", "units": "1", "urgency": "High",
            "hospital": "CMH", "city": "Larkana", "contact_phone": "0300-1234567"}
    for _ in range(5):
        c.post("/requests/new", data=good)
    r = c.post("/requests/new", data=good, follow_redirects=True)
    assert b"at most 5" in r.data
