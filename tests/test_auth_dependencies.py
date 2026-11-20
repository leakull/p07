import uuid

import pytest
from fastapi import HTTPException

from app.models import Employee, EmployeeRole
from app.routers.auth import require_permission, require_user


def make_employee(*, role: EmployeeRole = EmployeeRole.admin, is_active: bool = True) -> Employee:
    return Employee(
        id=uuid.uuid4(),
        full_name="Test User",
        role=role,
        email=f"{uuid.uuid4()}@example.com",
        password_hash="hashed",
        is_active=is_active,
    )


@pytest.mark.asyncio
async def test_require_user_raises_401_when_missing():
    with pytest.raises(HTTPException) as exc:
        await require_user(None)

    assert exc.value.status_code == 401
    assert exc.value.detail == "Not authenticated"


@pytest.mark.asyncio
async def test_require_user_raises_403_for_inactive_user():
    user = make_employee(is_active=False)

    with pytest.raises(HTTPException) as exc:
        await require_user(user)

    assert exc.value.status_code == 403
    assert exc.value.detail == "Inactive user"


@pytest.mark.asyncio
async def test_require_permission_allows_authorized_role():
    checker = require_permission("equipment", "read")
    user = make_employee(role=EmployeeRole.viewer)

    result = await checker(user)

    assert result.id == user.id


@pytest.mark.asyncio
async def test_require_permission_rejects_unauthorized_role():
    checker = require_permission("audit", "read")
    user = make_employee(role=EmployeeRole.viewer)

    with pytest.raises(HTTPException) as exc:
        await checker(user)

    assert exc.value.status_code == 403
    assert "cannot 'read' on 'audit'" in exc.value.detail
