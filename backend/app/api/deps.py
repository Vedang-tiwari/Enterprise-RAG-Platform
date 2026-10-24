"""API Dependencies for authentication, tenant context, and authorization."""
import time
from typing import Dict, Optional, Tuple
from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.config import settings
from backend.app.core.security import decode_token
from backend.app.db.session import get_db
from backend.app.models.user import User
from backend.app.models.organization import Organization, Membership

security_scheme = HTTPBearer(auto_error=False)

# In-memory sliding window rate limiter
# Key: client_id -> [timestamps]
_rate_limits: Dict[str, list] = {}


async def check_rate_limit(request: Request) -> None:
    """Enforces sliding-window rate limit."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    now = time.time()
    window = 60.0  # 1 minute

    timestamps = _rate_limits.setdefault(client_ip, [])
    # Evict timestamps older than 1 minute
    _rate_limits[client_ip] = [t for t in timestamps if now - t < window]

    if len(_rate_limits[client_ip]) >= settings.RATE_LIMIT_PER_MINUTE:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later."
        )
    _rate_limits[client_ip].append(now)


async def get_current_user(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Extracts and validates current authenticated user from Bearer JWT."""
    if not auth or not auth.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token required.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    payload = decode_token(auth.credentials)
    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token subject missing.")

    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User account disabled or not found.")

    return user


async def get_tenant_context(
    current_user: User = Depends(get_current_user),
    x_organization_id: Optional[str] = Header(None, alias="X-Organization-ID"),
    db: AsyncSession = Depends(get_db)
) -> Tuple[Organization, Membership]:
    """
    Resolves active Organization and user Membership for multi-tenancy enforcement.
    If X-Organization-ID is passed, checks membership. Otherwise, defaults to user's first organization.
    """
    if x_organization_id:
        stmt = (
            select(Membership, Organization)
            .join(Organization, Membership.organization_id == Organization.id)
            .where(
                Membership.user_id == current_user.id,
                Membership.organization_id == x_organization_id,
                Organization.is_active == True
            )
        )
        res = await db.execute(stmt)
        record = res.first()
        if not record:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to the specified organization."
            )
        membership, org = record
        return org, membership

    # Default to first organization
    stmt = (
        select(Membership, Organization)
        .join(Organization, Membership.organization_id == Organization.id)
        .where(
            Membership.user_id == current_user.id,
            Organization.is_active == True
        )
        .order_by(Membership.created_at.asc())
    )
    res = await db.execute(stmt)
    record = res.first()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not belong to any active organization."
        )
    membership, org = record
    return org, membership


def require_role(required_role: str):
    """RBAC dependency: checks if user has 'admin', 'member', etc."""
    async def role_checker(
        tenant: Tuple[Organization, Membership] = Depends(get_tenant_context)
    ) -> Tuple[Organization, Membership]:
        org, membership = tenant
        role_hierarchy = {"admin": 3, "member": 2, "viewer": 1}
        user_level = role_hierarchy.get(membership.role, 0)
        required_level = role_hierarchy.get(required_role, 2)

        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Action requires '{required_role}' privileges."
            )
        return org, membership
    return role_checker
