"""Organizations API router."""
import re
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.api.deps import get_current_user, require_role, get_tenant_context
from backend.app.db.session import get_db
from backend.app.models.user import User
from backend.app.models.organization import Organization, Membership
from backend.app.models.workspace import Workspace
from backend.app.schemas.organization import MemberAdd, MemberResponse, OrgCreate, OrgResponse

router = APIRouter(prefix="/organizations", tags=["Organizations"])


@router.post("", response_model=OrgResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    payload: OrgCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new isolated organization and assign creator as Admin."""
    slug = payload.slug or re.sub(r"[^a-zA-Z0-9]+", "-", payload.name.lower()).strip("-")
    slug = f"{slug}-{current_user.id[:6]}"

    org = Organization(
        name=payload.name,
        slug=slug,
        description=payload.description or ""
    )
    db.add(org)
    await db.flush()

    # Assign Admin membership
    membership = Membership(
        user_id=current_user.id,
        organization_id=org.id,
        role="admin"
    )
    db.add(membership)

    # Create default workspace
    ws = Workspace(
        name="General",
        slug="general",
        description="General knowledge workspace",
        organization_id=org.id
    )
    db.add(ws)

    await db.commit()
    await db.refresh(org)
    return org


@router.get("", response_model=List[OrgResponse])
async def list_user_organizations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all organizations the current user has access to."""
    stmt = (
        select(Organization)
        .join(Membership, Organization.id == Membership.organization_id)
        .where(Membership.user_id == current_user.id, Organization.is_active == True)
    )
    res = await db.execute(stmt)
    return res.scalars().all()


@router.get("/{org_id}", response_model=OrgResponse)
async def get_organization(
    org_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get organization details if user is a member."""
    stmt = (
        select(Organization)
        .join(Membership, Organization.id == Membership.organization_id)
        .where(Organization.id == org_id, Membership.user_id == current_user.id)
    )
    res = await db.execute(stmt)
    org = res.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found.")
    return org


@router.post("/{org_id}/members", response_model=MemberResponse, dependencies=[Depends(require_role("admin"))])
async def add_organization_member(
    org_id: str,
    payload: MemberAdd,
    db: AsyncSession = Depends(get_db)
):
    """Invite/Add a user to the organization with role (admin, member, viewer)."""
    # Find user by email
    u_stmt = select(User).where(User.email == payload.email)
    u_res = await db.execute(u_stmt)
    target_user = u_res.scalar_one_or_none()

    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with email '{payload.email}' does not exist on the platform."
        )

    # Check if membership already exists
    m_stmt = select(Membership).where(
        Membership.user_id == target_user.id,
        Membership.organization_id == org_id
    )
    m_res = await db.execute(m_stmt)
    if m_res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a member of this organization."
        )

    membership = Membership(
        user_id=target_user.id,
        organization_id=org_id,
        role=payload.role
    )
    db.add(membership)
    await db.commit()
    await db.refresh(membership)

    return MemberResponse(
        id=membership.id,
        user_id=target_user.id,
        email=target_user.email,
        full_name=target_user.full_name,
        role=membership.role,
        created_at=membership.created_at
    )
