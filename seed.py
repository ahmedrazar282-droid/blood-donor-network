"""Create demo data. Run once:  python seed.py
Admin login: admin@example.com (password from ADMIN_PASSWORD, or the default below; change it!)
Demo users:  Demo@12345
"""
import os

from app import create_app
from app.demo import seed_demo

app = create_app()

with app.app_context():
    if seed_demo(os.environ.get("ADMIN_PASSWORD") or "Admin@12345"):
        print("Seeded. Admin: admin@example.com. Demo users: ahmed@example.com, sara@example.com (Demo@12345).")
    else:
        print("Already seeded.")
