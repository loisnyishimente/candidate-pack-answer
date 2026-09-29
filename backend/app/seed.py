import json
import os
from pathlib import Path

from sqlalchemy import select

from .database import SessionLocal
from .models import Role, User
from .security import hash_password


def main():
    path = Path(os.getenv("SEED_USERS_PATH", "/seed/users.json"))
    with path.open() as handle: records = json.load(handle)
    with SessionLocal() as db:
        for data in records:
            email = data["email"].lower()
            user = db.scalar(select(User).where(User.email == email))
            if user: continue
            db.add(User(email=email, password_hash=hash_password(data["password"]), role=Role(data["role"]), name=data["name"], organisation=data.get("organisation")))
        db.commit()


if __name__ == "__main__": main()

