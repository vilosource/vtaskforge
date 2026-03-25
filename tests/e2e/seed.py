"""
Seed script for the E2E test stack.

Run INSIDE the api container:
    docker compose -f docker-compose.e2e.yml -p vtf-e2e exec -T api \\
        python -c "exec(open('/app/tests/e2e/seed.py').read())"

Creates known test state:
- Admin user + DRF token with a KNOWN key (e2e-test-token-12345)
- Project (id=e2e-project)
- Workplan + Milestone
- 5 tasks in various states
- Agent (id=e2e-executor)

The known token key avoids the need to pass the token from container to host.
"""
import os
import sys

# Bootstrap Django when run as a plain script inside the container.
# When exec'd via exec(open(...).read()) the Django setup has already happened
# if django.setup() was called in the outer scope, but we set up defensively.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "vtaskforge.settings.dev")

# Add the src directory to the path when run as a standalone script.
# When exec()'d inside a container, __file__ is not defined, so fall back to /app/src.
try:
    _src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src")
except NameError:
    _src_dir = "/app/src"
if os.path.isdir(_src_dir) and _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

import django  # noqa: E402

django.setup()

from django.contrib.auth.models import User  # noqa: E402
from rest_framework.authtoken.models import Token  # noqa: E402
from projects.models import Project  # noqa: E402
from workplans.models import Workplan, Milestone  # noqa: E402
from tasks.models import Task  # noqa: E402
from agents.models import Agent  # noqa: E402

# ---------------------------------------------------------------------------
# Admin user + token with KNOWN key so conftest doesn't need to parse output
# ---------------------------------------------------------------------------
E2E_TOKEN_KEY = "e2e-test-token-12345"

user, _ = User.objects.get_or_create(
    username="e2e-admin",
    defaults={"is_staff": True, "is_superuser": True},
)
user.set_password("e2e-admin-password")
user.save()

# Delete any old token so we can set the known key deterministically.
Token.objects.filter(user=user).delete()
token = Token.objects.create(user=user, key=E2E_TOKEN_KEY)

# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------
project, _ = Project.objects.get_or_create(
    id="e2e-project",
    defaults={"name": "E2E Test Project"},
)

# ---------------------------------------------------------------------------
# Workplan + Milestone
# ---------------------------------------------------------------------------
wp, _ = Workplan.objects.get_or_create(
    id="e2e-workplan",
    defaults={"project": project, "name": "E2E Workplan"},
)
ms, _ = Milestone.objects.get_or_create(
    id="e2e-milestone",
    defaults={"workplan": wp, "name": "E2E Milestone", "order": 0},
)

# ---------------------------------------------------------------------------
# Tasks in various states
# ---------------------------------------------------------------------------
Task.objects.get_or_create(
    id="e2e-todo-1",
    defaults={
        "title": "Task ready for claiming",
        "project": project,
        "workplan": wp,
        "milestone": ms,
        "status": "todo",
        "spec": "test: true",
        "needs_review_on_completion": False,
    },
)
Task.objects.get_or_create(
    id="e2e-todo-2",
    defaults={
        "title": "Second claimable task",
        "project": project,
        "workplan": wp,
        "milestone": ms,
        "status": "todo",
        "needs_review_on_completion": False,
    },
)
Task.objects.get_or_create(
    id="e2e-blocked",
    defaults={
        "title": "Blocked task",
        "project": project,
        "workplan": wp,
        "milestone": ms,
        "status": "blocked",
    },
)
Task.objects.get_or_create(
    id="e2e-review",
    defaults={
        "title": "Task pending review",
        "project": project,
        "workplan": wp,
        "milestone": ms,
        "status": "pending_completion_review",
        "needs_review_on_completion": True,
    },
)
Task.objects.get_or_create(
    id="e2e-draft",
    defaults={
        "title": "Draft task",
        "project": project,
        "workplan": wp,
        "milestone": ms,
        "status": "draft",
    },
)

# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------
agent, _ = Agent.objects.get_or_create(
    id="e2e-executor",
    defaults={"name": "e2e-executor", "status": "online", "tags": ["executor"]},
)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
task_count = Task.objects.count()
print(f"Seeded: project={project.id}, workplan={wp.id}, milestone={ms.id}")
print(f"  tasks={task_count}, agent={agent.id}, token={token.key}")
