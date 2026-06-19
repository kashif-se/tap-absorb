"""Shared test fixtures for tap-absorb."""

from __future__ import annotations

import pytest

SAMPLE_CONFIG = {
    "base_url": "https://rest.myabsorb.com",
    "private_key": "test-private-key",
    "username": "test-user",
    "password": "test-password",
    "start_date": "2023-01-01T00:00:00Z",
    "page_size": 100,
}

SAMPLE_TOKEN = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.test-token"

SAMPLE_AUTH_RESPONSE = SAMPLE_TOKEN  # Absorb returns raw token string


@pytest.fixture
def sample_config():
    return SAMPLE_CONFIG.copy()
