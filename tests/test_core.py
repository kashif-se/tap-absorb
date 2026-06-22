"""Core tap tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import responses as rsps_module

from tap_absorb.tap import TapAbsorb
from tests.conftest import SAMPLE_TOKEN

# ---------------------------------------------------------------------------
# Tap discovery / config validation
# ---------------------------------------------------------------------------


def test_tap_discovers_all_streams(sample_config):
    """TapAbsorb.discover_streams() should return the expected stream names."""
    tap = TapAbsorb(config=sample_config)
    stream_names = {s.name for s in tap.discover_streams()}

    expected = {
        "departments",
        "categories",
        "groups",
        "courses",
        "course_bundles",
        "curricula",
        "instructor_led_courses",
        "learning_paths",
        "users",
        "enrollments",
        "attendances",
        "certificates",
        "external_training",
    }
    assert expected == stream_names


def test_tap_missing_required_config():
    """Tap should raise an error when required keys are missing."""
    with pytest.raises(Exception):
        TapAbsorb(config={"base_url": "https://rest.myabsorb.com"})


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


@rsps_module.activate
def test_authenticator_fetches_token(sample_config):
    """AbsorbAuthenticator should POST /authenticate and cache the token."""
    rsps_module.add(
        rsps_module.POST,
        "https://rest.myabsorb.com/authenticate",
        json=SAMPLE_TOKEN,
        status=200,
    )

    tap = TapAbsorb(config=sample_config)
    stream = tap.streams["departments"]
    auth = stream.authenticator

    headers = auth.auth_headers
    assert headers["Authorization"] == SAMPLE_TOKEN
    assert headers["x-api-key"] == sample_config["private_key"]
    assert len(rsps_module.calls) == 1


@rsps_module.activate
def test_authenticator_caches_token(sample_config):
    """Second call to auth_headers should NOT re-authenticate."""
    rsps_module.add(
        rsps_module.POST,
        "https://rest.myabsorb.com/authenticate",
        json=SAMPLE_TOKEN,
        status=200,
    )

    tap = TapAbsorb(config=sample_config)
    stream = tap.streams["departments"]
    auth = stream.authenticator

    _ = auth.auth_headers
    _ = auth.auth_headers  # second call – should use cache

    assert len(rsps_module.calls) == 1  # only one auth call


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


def test_paginator_has_more_when_full_page():
    """Paginator should signal more pages when a full page was returned."""
    from tap_absorb.client import AbsorbPaginator

    paginator = AbsorbPaginator(page_size=100)
    mock_response = MagicMock()
    mock_response.json.return_value = {"users": [{"id": str(i)} for i in range(100)]}
    assert paginator.has_more(mock_response) is True


def test_paginator_no_more_on_partial_page():
    """Paginator should stop when fewer records than page_size are returned."""
    from tap_absorb.client import AbsorbPaginator

    paginator = AbsorbPaginator(page_size=100)
    mock_response = MagicMock()
    mock_response.json.return_value = {"users": [{"id": str(i)} for i in range(42)]}
    assert paginator.has_more(mock_response) is False


def test_paginator_no_more_on_empty_page():
    """Paginator should stop on an empty response."""
    from tap_absorb.client import AbsorbPaginator

    paginator = AbsorbPaginator(page_size=100)
    mock_response = MagicMock()
    mock_response.json.return_value = {"users": []}
    assert paginator.has_more(mock_response) is False


# ---------------------------------------------------------------------------
# Stream URL params
# ---------------------------------------------------------------------------


@rsps_module.activate
def test_stream_url_params_include_incremental_filter(sample_config):
    """get_url_params() should include _filter when start_date is configured."""
    rsps_module.add(
        rsps_module.POST,
        "https://rest.myabsorb.com/authenticate",
        json=SAMPLE_TOKEN,
        status=200,
    )

    tap = TapAbsorb(config=sample_config)
    stream = tap.streams["departments"]

    params = stream.get_url_params(context=None, next_page_token=0)

    assert "_limit" in params
    assert "_offset" in params
    assert "_sort" in params
    assert "_filter" in params
    assert "dateEdited ge datetime" in params["_filter"]


# ---------------------------------------------------------------------------
# Child stream context
# ---------------------------------------------------------------------------


def test_users_stream_provides_child_context(sample_config):
    """UsersStream.get_child_context() should return {user_id: ...}."""
    tap = TapAbsorb(config=sample_config)
    stream = tap.streams["users"]
    ctx = stream.get_child_context(
        record={"id": "abc-123", "email": "test@example.com"}, context=None
    )
    assert ctx == {"user_id": "abc-123"}


def test_enrollments_post_process_injects_user_id(sample_config):
    """UserEnrollmentsStream.post_process() should inject userId from context."""
    tap = TapAbsorb(config=sample_config)
    stream = tap.streams["enrollments"]
    row = {"id": "enroll-1", "courseId": "course-1"}
    result = stream.post_process(row, context={"user_id": "user-99"})
    assert result["userId"] == "user-99"
