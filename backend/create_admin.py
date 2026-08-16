"""
backend/create_admin.py
CLI utility to create a new Admin account or promote an existing user to Admin in SS SPARK / PaperGenius.

Usage:
  python create_admin.py --email admin@ssspark.ai --password AdminPassword123! --name "Administrator"
  python create_admin.py --promote user@example.com
"""

import sys
import argparse
import asyncio
from pathlib import Path

# Ensure backend dir is on path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv
load_dotenv()

from core.security import hash_password
from core.config import get_settings
from database.models import init_db
from database.user_models import (
    UserRecord,
    UserRole,
    UserStatus,
    AuthProvider,
    create_user,
    get_user_by_email,
    update_user,
)


async def main():
    settings = get_settings()
    await init_db(settings.MONGO_URI, settings.MONGO_DB_NAME)

    parser = argparse.ArgumentParser(description="Create or promote an Admin account for SS SPARK.")
    parser.add_argument("--email", type=str, help="Email address for the admin account")
    parser.add_argument("--password", type=str, help="Password for the admin account")
    parser.add_argument("--name", type=str, default="Administrator", help="Display name for the admin")
    parser.add_argument("--promote", type=str, help="Email of an existing user to promote to Admin")

    args = parser.parse_args()

    if args.promote:
        email = args.promote.lower().strip()
        existing = await get_user_by_email(email)
        if not existing:
            print(f"[-] User with email '{email}' not found in MongoDB.")
            sys.exit(1)

        await update_user(existing.id, {"role": UserRole.ADMIN.value})
        print(f"[+] Successfully promoted '{email}' ({existing.full_name}) to role: {UserRole.ADMIN.value}!")
        return

    email = args.email or "admin@ssspark.ai"
    password = args.password or "Admin@12345"
    name = args.name or "System Admin"

    email = email.lower().strip()
    existing = await get_user_by_email(email)

    if existing:
        await update_user(existing.id, {
            "role": UserRole.ADMIN.value,
            "status": UserStatus.ACTIVE.value,
            "hashed_password": hash_password(password),
            "full_name": name,
        })
        print(f"[+] Existing user '{email}' updated with role: ADMIN and new password.")
    else:
        new_admin = UserRecord(
            email=email,
            full_name=name,
            hashed_password=hash_password(password),
            role=UserRole.ADMIN,
            status=UserStatus.ACTIVE,
            provider=AuthProvider.LOCAL,
        )
        created = await create_user(new_admin)
        print(f"[+] New Admin account created successfully!")
        print(f"    - ID:       {created.id}")

    print(f"    - Email:    {email}")
    print(f"    - Password: {password}")
    print(f"    - Role:     admin")
    print(f"    - Portal:   http://localhost:8080/admin (or /login)")


if __name__ == "__main__":
    asyncio.run(main())
