"""Test setup: provide dummy values for required settings so app modules that
call get_settings() at import time work without a real .env (e.g. in CI).
These are never used to touch real infrastructure — the tests here exercise
pure functions only."""

import os

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-0123456789")
os.environ.setdefault("ENCRYPTION_KEY", "test-encryption-key")
os.environ.setdefault("FRONTEND_URL", "http://localhost:3000")
