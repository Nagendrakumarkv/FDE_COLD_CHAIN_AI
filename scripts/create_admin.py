"""Create an admin account with a bcrypt-hashed password.

Run from the project root:

    python -m scripts.create_admin

The password is typed at a hidden prompt, so it never appears in shell
history, source files or logs. The target database follows DB_TARGET.
"""

import getpass
import re
import sys

from agent.auth import MAX_PASSWORD_BYTES, hash_password
from tools import chat_store

MIN_PASSWORD_LENGTH = 12
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.@-]{3,100}$")


def main():
    username = input("Admin username: ").strip().lower()

    if not USERNAME_PATTERN.match(username):
        sys.exit(
            "Username must be 3-100 characters: letters, digits, "
            "and . _ @ -"
        )

    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm password: ")

    if password != confirm:
        sys.exit("Passwords do not match.")

    if len(password) < MIN_PASSWORD_LENGTH:
        sys.exit(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
        )

    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        sys.exit(f"Password must be at most {MAX_PASSWORD_BYTES} bytes.")

    chat_store.ensure_schema()

    if chat_store.get_admin_by_username(username):
        sys.exit("That username already exists.")

    admin_id = chat_store.create_admin(username, hash_password(password))

    print(f"Admin '{username}' created (id {admin_id}).")


if __name__ == "__main__":
    main()
