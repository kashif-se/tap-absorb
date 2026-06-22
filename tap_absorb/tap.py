"""Absorb LMS tap class."""

from __future__ import annotations

from typing import List

from singer_sdk import Tap
from singer_sdk import typing as th

from tap_absorb.streams import (
    AttendancesStream,
    CategoriesStream,
    CertificatesStream,
    CourseBundlesStream,
    CoursesStream,
    CurriculaStream,
    DepartmentsStream,
    ExternalTrainingStream,
    GroupsStream,
    InstructorLedCoursesStream,
    LearningPathsStream,
    UserEnrollmentsStream,
    UsersStream,
)


class TapAbsorb(Tap):
    """Singer tap for Absorb LMS.

    Reads data from the Absorb Integration API (v2) and emits Singer-compatible
    RECORD, STATE, and SCHEMA messages.

    Configuration
    -------------
    Provide the following keys in your ``tap-config.json`` (or Meltano config):

    - ``base_url``     – API root URL (default ``https://rest.myabsorb.com``)
    - ``private_key``  – X-API-Key issued from the Absorb portal
    - ``username``     – Admin username used for authentication
    - ``password``     – Admin password used for authentication
    - ``start_date``   – ISO 8601 date from which incremental syncs begin
                         (e.g. ``"2022-01-01T00:00:00Z"``)
    - ``page_size``    – Records per API page (default 500, max 1000)
    """

    name = "tap-absorb"

    config_jsonschema = th.PropertiesList(
        th.Property(
            "base_url",
            th.StringType,
            required=False,
            default="https://rest.myabsorb.com",
            description=(
                "Absorb API base URL. Use the region-specific endpoint for your "
                "environment. Supported regions: US, EU, AU, CA.  "
                "Example: 'https://rest.myabsorb.eu'"
            ),
        ),
        th.Property(
            "private_key",
            th.StringType,
            required=True,
            secret=True,
            description=(
                "Private API key obtained from the Absorb portal settings. "
                "Sent as the 'X-API-Key' header on every request."
            ),
        ),
        th.Property(
            "username",
            th.StringType,
            required=True,
            description="Admin username for the /authenticate endpoint.",
        ),
        th.Property(
            "password",
            th.StringType,
            required=True,
            secret=True,
            description="Admin password for the /authenticate endpoint.",
        ),
        th.Property(
            "start_date",
            th.DateTimeType,
            required=False,
            description=(
                "UTC datetime from which incremental extracts begin. "
                "Records with dateEdited >= start_date will be returned. "
                "Example: '2022-01-01T00:00:00Z'"
            ),
        ),
        th.Property(
            "page_size",
            th.IntegerType,
            required=False,
            default=500,
            description=(
                "Number of records fetched per API call (1–1000). "
                "Higher values reduce round-trips; lower values reduce memory usage."
            ),
        ),
        th.Property(
            "user_agent",
            th.StringType,
            required=False,
            default="tap-absorb/0.1.0 (https://kashifsohail.com)",
            description="User-Agent header sent with every request.",
        ),
    ).to_dict()

    def discover_streams(self) -> List:
        """Return all supported streams."""
        return [
            # Reference / dimension streams
            DepartmentsStream(self),
            CategoriesStream(self),
            GroupsStream(self),
            # Course catalog
            CoursesStream(self),
            CourseBundlesStream(self),
            CurriculaStream(self),
            InstructorLedCoursesStream(self),
            LearningPathsStream(self),
            # People
            UsersStream(self),
            # Fact / event streams
            UserEnrollmentsStream(self),   # child of UsersStream
            AttendancesStream(self),
            CertificatesStream(self),
            ExternalTrainingStream(self),
        ]


if __name__ == "__main__":
    TapAbsorb.cli()
