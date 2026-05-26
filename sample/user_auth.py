"""Scenario 4: KeyError — 사용자 인증 (중첩 객체 누락 필드)"""

import errordog.tracker  # noqa: F401


def build_session_token(user: dict) -> str:
    """Build a session token from user profile data."""
    profile = user["profile"]
    permissions = profile["permissions"]
    role = permissions["role"]  # bug: key missing for some users
    scope = permissions["scope"]
    return f"{user['id']}:{role}:{scope}"


def authenticate_users(users: list[dict]) -> list[str]:
    tokens = []
    for user in users:
        token = build_session_token(user)
        tokens.append(token)
        print(f"  Authenticated: {user['email']} → {token}")
    return tokens


users = [
    {
        "id": "u_001",
        "email": "admin@example.com",
        "profile": {"permissions": {"role": "admin", "scope": "full"}},
    },
    {
        "id": "u_002",
        "email": "viewer@example.com",
        "profile": {"permissions": {"scope": "read_only"}},  # bug: missing "role"
    },
]

authenticate_users(users)
