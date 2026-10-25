"""Create demo data. Run once:  python seed.py
Admin login: admin@example.com (password from ADMIN_PASSWORD or the default below; change it!)
Demo users:  Demo@12345
"""
import os
from datetime import date, timedelta

from app import create_app, db
from app.models import BloodRequest, Donor, User, utcnow

app = create_app()

DONORS = [("Ahmed Raza", "ahmed@example.com", "O+", "Naushahro Feroze", 120),
          ("Sara Khan", "sara@example.com", "A+", "Sukkur", 200),
          ("Bilal Memon", "bilal@example.com", "O-", "Sukkur", 95),
          ("Imran Shaikh", "imran@example.com", "B+", "Larkana", 40),
          ("Zainab Soomro", "zainab@example.com", "AB+", "Hyderabad", 150),
          ("Farah Abro", "farah@example.com", "O+", "Sukkur", 100)]

with app.app_context():
    if User.query.filter_by(email="admin@example.com").first():
        print("Already seeded.")
        raise SystemExit
    admin = User(full_name="Admin", email="admin@example.com", phone="0300-0000000", role="admin")
    admin.set_password(os.environ.get("ADMIN_PASSWORD") or "Admin@12345")
    db.session.add(admin)
    users = []
    for i, (name, email, blood, city, days) in enumerate(DONORS):
        u = User(full_name=name, email=email, phone=f"030{i}-100000{i}")
        u.set_password("Demo@12345")
        db.session.add(u)
        db.session.flush()
        db.session.add(Donor(user_id=u.id, blood_type=blood, city=city,
                             last_donation_date=date.today() - timedelta(days=days)))
        users.append(u)
    db.session.add(BloodRequest(requester_id=users[1].id, patient_name="Mrs. Rubina", blood_type="O+", units=2,
                                urgency="Critical", hospital="Civil Hospital", city="Sukkur",
                                contact_phone="0301-2223334", is_verified=True,
                                expires_at=utcnow() + timedelta(hours=24)))
    db.session.add(BloodRequest(requester_id=users[0].id, patient_name="Ali Hassan", blood_type="B+", units=1,
                                urgency="High", hospital="Chandka Medical Hospital", city="Larkana",
                                contact_phone="0300-9998887", expires_at=utcnow() + timedelta(hours=48)))
    db.session.commit()
    print("Seeded. Admin: admin@example.com. Demo users: ahmed@example.com, sara@example.com (Demo@12345).")
