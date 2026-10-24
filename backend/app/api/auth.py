"""Authentication API endpoints."""
import re
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.config import settings
from backend.app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password
)
from backend.app.db.session import get_db
from backend.app.models.user import User
from backend.app.models.organization import Organization, Membership
from backend.app.models.workspace import Workspace
from backend.app.schemas.auth import (
    RefreshTokenRequest,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse
)
from backend.app.api.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: UserRegister, db: AsyncSession = Depends(get_db)):
    """Register a new user and bootstrap their default organization and workspace."""
    # Check if user already exists
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists."
        )

    # 1. Create User
    new_user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name or payload.email.split("@")[0]
    )
    db.add(new_user)
    await db.flush()

    # 2. Create Default Organization
    org_name = payload.organization_name or f"{new_user.full_name}'s Org"
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", org_name.lower()).strip("-")
    slug = f"{slug}-{new_user.id[:8]}"

    org = Organization(name=org_name, slug=slug)
    db.add(org)
    await db.flush()

    # 3. Create Admin Membership
    membership = Membership(
        user_id=new_user.id,
        organization_id=org.id,
        role="admin"
    )
    db.add(membership)

    # 4. Create Default "General" Workspace
    workspace = Workspace(
        name="General",
        slug="general",
        description="Default workspace for organizational knowledge",
        organization_id=org.id
    )
    db.add(workspace)

    await db.commit()

    # Generate Tokens
    claims = {"org_id": org.id, "role": "admin"}
    access_token = create_access_token(subject=new_user.id, claims=claims)
    refresh_token = create_refresh_token(subject=new_user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/login", response_model=TokenResponse)
async def login(payload: UserLogin, db: AsyncSession = Depends(get_db)):
    """Authenticate with email and password to receive JWT credentials."""
    stmt = select(User).where(User.email == payload.email)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password."
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive."
        )

    # Fetch user's primary organization membership
    m_stmt = select(Membership).where(Membership.user_id == user.id).order_by(Membership.created_at.asc())
    m_res = await db.execute(m_stmt)
    membership = m_res.scalars().first()

    claims = {}
    if membership:
        claims = {"org_id": membership.organization_id, "role": membership.role}

    access_token = create_access_token(subject=user.id, claims=claims)
    refresh_token = create_refresh_token(subject=user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(payload: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    """Exchange a valid refresh token for a fresh access token."""
    decoded = decode_token(payload.refresh_token)
    if not decoded or decoded.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token."
        )

    user_id = decoded.get("sub")
    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account no longer active."
        )

    m_stmt = select(Membership).where(Membership.user_id == user.id).order_by(Membership.created_at.asc())
    m_res = await db.execute(m_stmt)
    membership = m_res.scalars().first()
    claims = {"org_id": membership.organization_id, "role": membership.role} if membership else {}

    new_access_token = create_access_token(subject=user.id, claims=claims)
    new_refresh_token = create_refresh_token(subject=user.id)

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    """Log out current user (client destroys stored tokens)."""
    return {"message": "Successfully logged out."}


@router.get("/me")
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve current user profile with active organization memberships."""
    stmt = (
        select(Membership, Organization)
        .join(Organization, Membership.organization_id == Organization.id)
        .where(Membership.user_id == current_user.id)
    )
    res = await db.execute(stmt)
    memberships_data = []
    for m, o in res.all():
        memberships_data.append({
            "membership_id": m.id,
            "role": m.role,
            "organization": {
                "id": o.id,
                "name": o.name,
                "slug": o.slug,
                "description": o.description
            }
        })

    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "is_active": current_user.is_active,
        "organizations": memberships_data
    }
