"""Absorb LMS REST client: authenticator, paginator, and base stream."""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Generator, Iterable, Optional

import backoff
import requests
from singer_sdk.exceptions import FatalAPIError, RetriableAPIError
from singer_sdk.pagination import BasePageNumberPaginator
from singer_sdk.streams import RESTStream

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Authenticator
# ---------------------------------------------------------------------------

class AbsorbAuthenticator:
    """Handles the Absorb /authenticate flow.

    The Absorb API uses a private-key + username/password authentication
    that returns a raw bearer token (valid for 4 hours).  This authenticator
    caches the token and refreshes it automatically before expiry.

    Token is cached at the CLASS level (keyed by private_key) so that all
    stream instances within a single tap run share one token and only
    authenticate once per 4-hour window.

    NOTE: This class does NOT inherit ``APIAuthenticatorBase`` intentionally.
    Older singer-sdk versions set ``self.auth_headers = {}`` as an instance
    attribute inside ``__init__``, which conflicts with the ``@property``
    descriptor of the same name and raises ``AttributeError: can't set
    attribute``.  A standalone class with the same public interface avoids
    this entirely.
    """

    # Refresh 60 s before the 4-hour TTL to avoid race conditions
    TOKEN_TTL_SECONDS: int = 4 * 3600 - 60

    # Class-level token cache: private_key → (token, expires_at)
    # Shared across ALL stream instances in the same process.
    _token_cache: dict[str, tuple[str, float]] = {}

    def __init__(self, stream: RESTStream) -> None:
        self._stream = stream

    # ------------------------------------------------------------------
    # Delegation helpers (mirrors APIAuthenticatorBase interface)
    # ------------------------------------------------------------------

    @property
    def config(self) -> dict:
        return self._stream.config  # type: ignore[return-value]

    @property
    def logger(self):  # noqa: ANN201
        return self._stream.logger

    # ------------------------------------------------------------------
    # requests.auth.AuthBase interface
    # ------------------------------------------------------------------

    def __call__(self, r: requests.PreparedRequest) -> requests.PreparedRequest:
        """Apply auth headers to an outgoing PreparedRequest.

        The singer-sdk passes ``self.authenticator`` as the ``auth=`` argument
        to ``requests``, which then calls ``auth(prepared_request)``.  This
        method satisfies that contract.
        """
        if self._token_needs_refresh():
            self._refresh_token()
        token, _ = self._token_cache[self.config["private_key"]]
        r.headers["Authorization"] = token
        r.headers["x-api-key"] = self.config["private_key"]
        return r

    @property
    def auth_headers(self) -> dict[str, str]:
        """Convenience property; mirrors the __call__ output."""
        if self._token_needs_refresh():
            self._refresh_token()
        token, _ = self._token_cache[self.config["private_key"]]
        return {
            "Authorization": token,
            "x-api-key": self.config["private_key"],
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _token_needs_refresh(self) -> bool:
        key = self.config["private_key"]
        entry = self._token_cache.get(key)
        if entry is None:
            return True
        _, expires_at = entry
        return time.monotonic() >= expires_at

    @backoff.on_exception(
        backoff.expo,
        (requests.exceptions.ConnectionError, requests.exceptions.Timeout),
        max_tries=3,
        factor=2,
        jitter=backoff.full_jitter,
    )
    def _refresh_token(self) -> None:
        base_url = self.config.get("base_url", "https://rest.myabsorb.com")
        url = f"{base_url}/authenticate"
        payload = {
            "privateKey": self.config["private_key"],
            "username": self.config["username"],
            "password": self.config["password"],
        }
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.config["private_key"],
        }

        logger.debug("Refreshing Absorb authentication token.")
        response = requests.post(url, json=payload, headers=headers, timeout=30)

        if response.status_code == 401:
            raise FatalAPIError("Absorb authentication failed (401). Check credentials.")
        response.raise_for_status()

        # The /authenticate endpoint returns the raw token string as the body
        token = response.json()
        expires_at = time.monotonic() + self.TOKEN_TTL_SECONDS
        AbsorbAuthenticator._token_cache[self.config["private_key"]] = (token, expires_at)
        logger.info("Absorb token refreshed, valid for ~4 hours.")


# ---------------------------------------------------------------------------
# Paginator
# ---------------------------------------------------------------------------

class AbsorbPaginator(BasePageNumberPaginator):
    """Page-number paginator for the Absorb API.

    Absorb uses ``_offset`` (0-indexed page number) and ``_limit`` (page size).
    We stop when the API returns fewer records than the requested page size.
    """

    def __init__(self, page_size: int, start_value: int = 0) -> None:
        super().__init__(start_value=start_value)
        self._page_size = page_size

    def has_more(self, response: requests.Response) -> bool:  # type: ignore[override]
        if not response.ok:
            return False
        try:
            data = response.json()
        except Exception:
            return False
        # The response body is an object; find the first list value.
        for value in data.values():
            if isinstance(value, list):
                return len(value) >= self._page_size
        return False


# ---------------------------------------------------------------------------
# Base stream
# ---------------------------------------------------------------------------

class AbsorbStream(RESTStream):
    """Base class for all Absorb LMS streams.

    Provides:
    - Token-based authentication via :class:`AbsorbAuthenticator`
    - Page-based pagination via :class:`AbsorbPaginator`
    - Incremental replication using ``dateEdited`` + Absorb's ``_filter`` param
    - Automatic retry on HTTP 429 (rate-limit) and 5xx errors
    - ``x-api-version: 2`` header on every request
    """

    # Each subclass sets the JSON key whose value is the list of records
    # e.g. "departments", "users", "courses" …
    data_key: str = ""

    # Default page size (Absorb max is 1000)
    page_size: int = 500

    @property
    def url_base(self) -> str:
        return self.config.get("base_url", "https://rest.myabsorb.com")

    _authenticator: Optional[AbsorbAuthenticator] = None

    @property
    def authenticator(self) -> AbsorbAuthenticator:
        if self._authenticator is None:
            self._authenticator = AbsorbAuthenticator(stream=self)
        return self._authenticator

    @property
    def http_headers(self) -> dict:
        # Auth headers (Authorization, x-api-key) are injected by
        # AbsorbAuthenticator.__call__ via the requests auth= mechanism.
        # Only set non-auth headers here to avoid applying them twice.
        return {
            "Content-Type": "application/json",
            "x-api-version": "2",
        }

    # ------------------------------------------------------------------
    # Pagination
    # ------------------------------------------------------------------

    def get_new_paginator(self) -> AbsorbPaginator:
        return AbsorbPaginator(page_size=self.page_size)

    def get_url_params(
        self,
        context: Optional[dict],
        next_page_token: Optional[int],
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "_limit": self.page_size,
            "_offset": next_page_token or 0,
            "_sort": "dateEdited",  # stable sort for incremental safety
        }

        # Incremental replication filter
        start_value = self.get_starting_replication_key_value(context)
        if start_value:
            # OData datetime filter: dateEdited ge datetime'YYYY-MM-DDTHH:MM:SSZ'
            params["_filter"] = f"dateEdited ge datetime'{start_value}'"

        return params

    # ------------------------------------------------------------------
    # Record extraction
    # ------------------------------------------------------------------

    def parse_response(self, response: requests.Response) -> Iterable[dict]:
        # 403/422 are handled in validate_response (warning logged, no raise).
        # Return early here so we emit zero records and move on.
        if response.status_code in (403, 422):
            return
        data = response.json()
        if self.data_key and isinstance(data, dict):
            yield from data.get(self.data_key, [])
        elif isinstance(data, list):
            yield from data
        else:
            # Fallback: yield the first list value found
            for value in data.values():
                if isinstance(value, list):
                    yield from value
                    return

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------

    def validate_response(self, response: requests.Response) -> None:
        if response.status_code == 403:
            # Endpoint not enabled for this Absorb account/plan (e.g. ILT module).
            self.logger.warning(
                "Access denied (403) for stream '%s' at %s. "
                "This endpoint may require a module or permission not enabled on "
                "your Absorb account. Skipping.",
                self.name,
                response.url,
            )
            return  # parse_response will yield nothing
        if response.status_code == 422:
            # Unprocessable Entity — endpoint likely doesn't support one of the
            # query params we sent (e.g. _sort=dateEdited or _filter OData syntax).
            self.logger.warning(
                "Unprocessable request (422) for stream '%s' at %s. "
                "This endpoint may not support the _sort or _filter params. Skipping.",
                self.name,
                response.url,
            )
            return  # parse_response will yield nothing
        if response.status_code == 429:
            msg = (
                f"Rate limited by Absorb API (429). "
                f"Retry-After: {response.headers.get('Retry-After', 'unknown')}s"
            )
            raise RetriableAPIError(msg, response=response)
        if response.status_code in (500, 502, 503, 504):
            raise RetriableAPIError(
                f"Server error {response.status_code} from Absorb API.",
                response=response,
            )
        super().validate_response(response)

    def backoff_wait_generator(self) -> Generator[float, None, None]:
        return backoff.expo(factor=2, base=2, max_value=60)  # type: ignore[return-value]

    def backoff_max_tries(self) -> int:
        return 5
