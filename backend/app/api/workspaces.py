"""Workspaces API router."""
import re
from typing import List, Tuple
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.api.deps import get_tenant_context, require_role
from backend.app.db.session import get_db
from backend.app.models.organization import Organization, Membership
from backend.app.models.workspace import Workspace
from backend.app.schemas.workspace import WorkspaceCreate, WorkspaceResponse

router = APIRouter(prefix="/workspaces", tags=["Workspaces"])


@router.post("", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    payload: WorkspaceCreate,
    tenant: Tuple[Organization, Membership] = Depends(require_role("member")),
    db: AsyncSession = Depends(get_db)
):
    """Create a new departmental workspace inside the current organization."""
    org, _ = tenant
    slug = payload.slug or re.sub(r"[^a-zA-Z0-9]+", "-", payload.name.lower()).strip("-")

    # Check for slug collision within org
    existing = await db.execute(
        select(Workspace).where(Workspace.organization_id == org.id, Workspace.slug == slug)
    )
    if existing.scalar_one_or_none():
        slug = f"{slug}-{org.id[:4]}"

    workspace = Workspace(
        name=payload.name,
        slug=slug,
        description=payload.description or "",
        organization_id=org.id
    )
    db.add(workspace)
    await db.commit()
    await db.refresh(workspace)
    return workspace


@router.get("", response_model=List[WorkspaceResponse])
async def list_workspaces(
    tenant: Tuple[Organization, Membership] = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    """List all workspaces within the active organization."""
    org, _ = tenant
    stmt = select(Workspace).where(Workspace.organization_id == org.id).order_by(Workspace.created_at.desc())
    res = await db.execute(stmt)
    return res.scalars().all()


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: str,
    tenant: Tuple[Organization, Membership] = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve details for a specific workspace within active organization."""
    org, _ = tenant
    stmt = select(Workspace).where(Workspace.id == workspace_id, Workspace.organization_id == org.id)
    res = await db.execute(stmt)
    ws = res.scalar_one_or_none()
    if not ws:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")
    return ws


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace(
    workspace_id: str,
    tenant: Tuple[Organization, Membership] = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db)
):
    """Delete a workspace and all its documents (Admin only)."""
    org, _ = tenant
    stmt = select(Workspace).where(Workspace.id == workspace_id, Workspace.organization_id == org.id)
    res = await db.execute(stmt)
    ws = res.scalar_one_or_none()
    if not ws:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")

    await db.delete(ws)
    await db.commit()
    return None
