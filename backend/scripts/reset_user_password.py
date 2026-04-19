import argparse
import asyncio
import getpass
import os
import sys
from datetime import datetime, timezone

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app.core.security import hash_password
from app.database import AsyncSessionLocal
from app.models.refresh_token import RefreshToken
from app.models.user import User


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reset a user password by username or email.")
    parser.add_argument(
        "--login",
        required=True,
        help="Username or email of the account to reset.",
    )
    parser.add_argument(
        "--password",
        default=None,
        help="New password. If omitted, prompt securely.",
    )
    parser.add_argument(
        "--keep-refresh-tokens",
        action="store_true",
        help="Do not revoke existing refresh tokens.",
    )
    return parser.parse_args()


async def reset_password(login: str, new_password: str, keep_refresh_tokens: bool) -> int:
    async with AsyncSessionLocal() as db:  # type: AsyncSession
        result = await db.execute(select(User).where(or_(User.username == login, User.email == login)))
        user = result.scalar_one_or_none()
        if user is None:
            raise ValueError(f"User not found: {login}")

        user.password_hash = hash_password(new_password)

        revoked_count = 0
        if not keep_refresh_tokens:
            revoke_stmt = (
                update(RefreshToken)
                .where(
                    RefreshToken.user_id == user.id,
                    RefreshToken.revoked_at.is_(None),
                )
                .values(revoked_at=datetime.now(timezone.utc))
            )
            revoke_result = await db.execute(revoke_stmt)
            revoked_count = int(revoke_result.rowcount or 0)

        await db.commit()
        return revoked_count


def main() -> None:
    args = parse_args()

    password = args.password
    if not password:
        first = getpass.getpass("New password: ")
        second = getpass.getpass("Confirm password: ")
        if first != second:
            raise SystemExit("Passwords do not match.")
        password = first

    if len(password) < 8:
        raise SystemExit("Password must be at least 8 characters.")

    revoked = asyncio.run(
        reset_password(
            login=args.login.strip(),
            new_password=password,
            keep_refresh_tokens=args.keep_refresh_tokens,
        )
    )
    print(f"Password reset completed. Revoked refresh tokens: {revoked}")


if __name__ == "__main__":
    main()
