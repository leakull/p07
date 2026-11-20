from datetime import datetime, timedelta
from typing import Optional, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
# Заменяем passlib на argon2
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Убедитесь, что пути импорта соответствуют вашей структуре (напр. app.database)
from app.database import get_db, settings
from app.models import Employee, EmployeeRole
from app.schemas import TokenResponse, LoginRequest

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Инициализируем Argon2 hasher
ph = PasswordHasher()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)

# Role-based permissions (оставляем без изменений)
ROLE_PERMISSIONS: Dict[EmployeeRole, Dict[str, List[str]]] = {
    EmployeeRole.admin: {
        "equipment": ["read", "write", "update", "move", "decommission"],
        "telemetry": ["read"],
        "maintenance": ["read", "write"],
        "audit": ["read"],
        "employees": ["read", "write"],
        "costs": ["read"],
        "locations": ["read"],
    },
    EmployeeRole.engineer: {
        "equipment": ["read", "update"],
        "telemetry": ["read", "write"],
        "maintenance": ["read", "write"],
        "audit": [],
        "employees": [],
        "costs": [],
        "locations": ["read"],
    },
    EmployeeRole.storekeeper: {
        "equipment": ["read", "write", "move"],
        "telemetry": [],
        "maintenance": ["read"],
        "audit": [],
        "employees": [],
        "costs": [],
        "locations": ["read", "write"],
    },
    EmployeeRole.auditor: {
        "equipment": ["read"],
        "telemetry": ["read"],
        "maintenance": ["read"],
        "audit": ["read"],
        "employees": ["read"],
        "costs": ["read"],
        "locations": ["read"],
    },
    EmployeeRole.viewer: {
        "equipment": ["read"],
        "telemetry": ["read"],
        "maintenance": ["read"],
        "audit": [],
        "employees": [],
        "costs": [],
        "locations": ["read"],
    },
}


# --- Функции хеширования ---

def verify_password(plain: str, hashed: str) -> bool:
    """Проверка пароля с использованием Argon2."""
    try:
        return ph.verify(hashed, plain)
    except (VerifyMismatchError, Exception):
        return False


def get_password_hash(password: str) -> str:
    """Генерация хеша Argon2."""
    return ph.hash(password)


# --- Работа с JWT ---

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


# --- Зависимости (Dependencies) ---

async def get_current_user(
        token: Optional[str] = Depends(oauth2_scheme),
        db: AsyncSession = Depends(get_db)
) -> Optional[Employee]:
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if not user_id:
            return None
    except JWTError:
        return None

    result = await db.execute(select(Employee).where(Employee.id == user_id))
    return result.scalar_one_or_none()


async def require_user(current_user: Optional[Employee] = Depends(get_current_user)) -> Employee:
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")
    return current_user


def require_permission(resource: str, action: str):
    async def checker(user: Employee = Depends(require_user)) -> Employee:
        perms = ROLE_PERMISSIONS.get(user.role, {})
        allowed = perms.get(resource, [])
        if action not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role.value}' cannot '{action}' on '{resource}'"
            )
        return user

    return checker


# --- Эндпоинты ---

@router.post("/token", response_model=TokenResponse)
async def login(form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Employee).where(Employee.email == form.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account inactive")

    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    return TokenResponse(
        access_token=token,
        role=user.role.value,
        user_id=str(user.id),
        full_name=user.full_name,
    )


@router.post("/login", response_model=TokenResponse)
async def login_json(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Employee).where(Employee.email == req.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    return TokenResponse(
        access_token=token,
        role=user.role.value,
        user_id=str(user.id),
        full_name=user.full_name,
    )


@router.get("/me")
async def me(user: Employee = Depends(require_user)):
    perms = ROLE_PERMISSIONS.get(user.role, {})
    return {
        "id": str(user.id),
        "full_name": user.full_name,
        "email": user.email,
        "role": user.role.value,
        "department_id": str(user.department_id) if user.department_id else None,
        "permissions": perms,
    }


@router.get("/permissions")
async def get_all_permissions():
    """Public endpoint: returns role-permission matrix for UI display."""
    return {
        role.value: perms
        for role, perms in ROLE_PERMISSIONS.items()
    }
    