"""Absorb LMS stream definitions."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from tap_absorb.client import AbsorbStream

logger = logging.getLogger(__name__)

SCHEMAS_DIR = Path(__file__).parent / "schemas"


# ---------------------------------------------------------------------------
# Top-level paginated streams
# ---------------------------------------------------------------------------


class DepartmentsStream(AbsorbStream):
    """Departments in the Absorb LMS.

    Endpoint: GET /departments
    Docs: https://docs.myabsorb.com/integration-api/v2/docs/departments
    """

    name = "departments"
    path = "/departments"
    primary_keys = ["id"]
    replication_key = "dateEdited"
    data_key = "departments"
    schema_filepath = SCHEMAS_DIR / "departments.json"


class UsersStream(AbsorbStream):
    """Learner and admin user accounts.

    Endpoint: GET /users
    Docs: https://docs.myabsorb.com/integration-api/v2/docs/users

    This stream is the *parent* of :class:`UserEnrollmentsStream`.
    """

    name = "users"
    path = "/users"
    primary_keys = ["id"]
    replication_key = "dateEdited"
    # is_sorted=True tells the SDK records arrive in ascending replication-key
    # order (we request _sort=dateEdited).  Without this the SDK cannot safely
    # advance the bookmark when a child stream (enrollments) is selected and
    # would fall back to a full-table sync of users every run.
    is_sorted = True
    data_key = "users"
    schema_filepath = SCHEMAS_DIR / "users.json"

    def get_child_context(self, record: dict, context: Optional[dict]) -> dict:
        """Pass the user ID to child enrollment stream."""
        return {"user_id": record["id"]}


class CoursesStream(AbsorbStream):
    """All course types (online, ILT, bundle, curriculum …).

    Endpoint: GET /courses
    Docs: https://docs.myabsorb.com/integration-api/v2/docs/courses
    """

    name = "courses"
    path = "/courses"
    primary_keys = ["id"]
    replication_key = "dateEdited"
    data_key = "courses"
    schema_filepath = SCHEMAS_DIR / "courses.json"


class CategoriesStream(AbsorbStream):
    """Course categories / taxonomy.

    Endpoint: GET /categories
    Docs: https://docs.myabsorb.com/integration-api/v2/docs/categories
    """

    name = "categories"
    path = "/categories"
    primary_keys = ["id"]
    replication_key = "dateEdited"
    data_key = "categories"
    schema_filepath = SCHEMAS_DIR / "categories.json"


class GroupsStream(AbsorbStream):
    """Static and dynamic user groups.

    Endpoint: GET /groups
    Docs: https://docs.myabsorb.com/integration-api/v2/docs/groups
    """

    name = "groups"
    path = "/groups"
    primary_keys = ["id"]
    replication_key = "dateEdited"
    data_key = "groups"
    schema_filepath = SCHEMAS_DIR / "groups.json"


class LearningPathsStream(AbsorbStream):
    """Ordered sequences of courses.

    Endpoint: GET /learningPaths
    Docs: https://docs.myabsorb.com/integration-api/v2/docs/learning-paths
    """

    name = "learning_paths"
    path = "/learningPaths"
    primary_keys = ["id"]
    replication_key = "dateEdited"
    data_key = "learningPaths"
    schema_filepath = SCHEMAS_DIR / "learning_paths.json"


class CourseBundlesStream(AbsorbStream):
    """Bundles of courses sold / assigned together.

    Endpoint: GET /courseBundles
    Docs: https://docs.myabsorb.com/integration-api/v2/docs/courses/course-bundles
    """

    name = "course_bundles"
    path = "/courseBundles"
    primary_keys = ["id"]
    replication_key = "dateEdited"
    data_key = "courseBundles"
    schema_filepath = SCHEMAS_DIR / "course_bundles.json"


class CurriculaStream(AbsorbStream):
    """Structured curricula (required course sequences).

    Endpoint: GET /curricula
    Docs: https://docs.myabsorb.com/integration-api/v2/docs/courses/curricula
    """

    name = "curricula"
    path = "/curricula"
    primary_keys = ["id"]
    replication_key = "dateEdited"
    data_key = "curricula"
    schema_filepath = SCHEMAS_DIR / "curricula.json"


class InstructorLedCoursesStream(AbsorbStream):
    """Instructor-led (classroom/virtual) courses.

    Endpoint: GET /instructorLedCourses
    Docs: https://docs.myabsorb.com/integration-api/v2/docs/courses/instructor-led-courses
    """

    name = "instructor_led_courses"
    path = "/instructorLedCourses"
    primary_keys = ["id"]
    replication_key = "dateEdited"
    data_key = "instructorLedCourses"
    schema_filepath = SCHEMAS_DIR / "instructor_led_courses.json"


class AttendancesStream(AbsorbStream):
    """ILT session attendance records.

    Endpoint: GET /attendances
    Docs: https://docs.myabsorb.com/integration-api/v2/docs/attendances
    """

    name = "attendances"
    path = "/attendances"
    primary_keys = ["id"]
    replication_key = "dateEdited"
    data_key = "attendances"
    schema_filepath = SCHEMAS_DIR / "attendances.json"


class ExternalTrainingStream(AbsorbStream):
    """External training records submitted by learners.

    Endpoint: GET /externalTrainings
    Docs: https://docs.myabsorb.com/integration-api/v2/docs/external-training
    """

    name = "external_training"
    path = "/externalTrainings"
    primary_keys = ["id"]
    replication_key = "dateEdited"
    data_key = "externalTrainings"
    schema_filepath = SCHEMAS_DIR / "external_training.json"


class CertificatesStream(AbsorbStream):
    """Certificates issued to learners upon course completion.

    Endpoint: GET /certificates
    Docs: https://docs.myabsorb.com/integration-api/v2/docs/certificates
    """

    name = "certificates"
    path = "/certificates"
    primary_keys = ["id"]
    replication_key = "dateEdited"
    data_key = "certificates"
    schema_filepath = SCHEMAS_DIR / "certificates.json"


# ---------------------------------------------------------------------------
# Child streams (require a parent record's context)
# ---------------------------------------------------------------------------


class UserEnrollmentsStream(AbsorbStream):
    """Course enrollment records for a specific user.

    Endpoint: GET /users/{user_id}/enrollments
    Docs: https://docs.myabsorb.com/integration-api/v2/docs/enrollments

    This is a *child* stream of :class:`UsersStream`.  For each user returned
    by the parent stream, Meltano SDK will call this stream with the user's
    ``id`` injected into the URL via ``context['user_id']``.

    Replication strategy: ``INCREMENTAL`` on ``dateEdited``.  The replication
    state is partitioned by ``user_id`` so each user's watermark is tracked
    independently.
    """

    name = "enrollments"
    path = "/users/{user_id}/enrollments"
    primary_keys = ["id"]
    replication_key = "dateEdited"
    data_key = "enrollments"
    schema_filepath = SCHEMAS_DIR / "enrollments.json"

    # Declare the parent stream so the SDK wires up context injection
    parent_stream_type = UsersStream

    # Store a separate bookmark per user_id partition
    state_partitioning_keys = ["user_id"]

    # Don't let the parent's replication key filter child requests
    ignore_parent_replication_key = True

    def get_url_params(
        self,
        context: Optional[dict],
        next_page_token: Optional[int],
    ) -> Dict[str, Any]:
        params = super().get_url_params(context, next_page_token)
        # Enrollments endpoint does not need the user_id in params;
        # it is already encoded in the URL path.
        return params

    def post_process(self, row: dict, context: Optional[dict] = None) -> Optional[dict]:
        """Inject the parent user_id into every enrollment record."""
        if context and "user_id" in context:
            row.setdefault("userId", context["user_id"])
        return row
