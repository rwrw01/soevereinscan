import re
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_session
from app.models import Scan
from app.schemas import ScanRequest, ScanResponse, ScanResultResponse

router = APIRouter(prefix="/api")


@router.post("/scan", response_model=ScanResponse, status_code=201)
async def start_scan(
    request: ScanRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    # Check for recent scan of same URL (deduplication: 24h cache)
    recent_cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    existing = await session.execute(
        select(Scan).where(
            Scan.url == str(request.url),
            Scan.status == "done",
            Scan.created_at > recent_cutoff,
        ).order_by(Scan.created_at.desc()).limit(1)
    )
    cached_scan = existing.scalar_one_or_none()
    if cached_scan:
        return cached_scan

    from app.main import get_orchestrator
    orchestrator = get_orchestrator()

    scan = await orchestrator.start_scan(session, str(request.url))
    background_tasks.add_task(_process_scan_background, scan.id)
    return scan


async def _process_scan_background(scan_id: uuid.UUID):
    from app.database import async_session
    from app.main import get_orchestrator

    orchestrator = get_orchestrator()
    async with async_session() as session:
        await orchestrator.process_scan(session, scan_id)


class EmailRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", v):
            raise ValueError("Ongeldig emailadres")
        return v


@router.get("/scan/{scan_id}", response_model=ScanResultResponse)
async def get_scan(
    scan_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Scan).options(selectinload(Scan.ip_analyses)).where(Scan.id == scan_id)
    result = await session.execute(stmt)
    scan = result.scalar_one_or_none()

    if not scan:
        raise HTTPException(status_code=404, detail="Scan niet gevonden")

    return scan


@router.post("/scan/{scan_id}/email", status_code=202)
async def send_report_email(
    scan_id: uuid.UUID,
    request: EmailRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    scan = await session.get(Scan, scan_id)
    if not scan or scan.status != "done":
        raise HTTPException(
            status_code=404,
            detail="Scan niet gevonden of nog niet afgerond",
        )

    background_tasks.add_task(
        _send_report_email,
        scan_id=scan_id,
        email=request.email,
        url=scan.url,
    )
    return {"message": "Rapport wordt per email verzonden"}


async def _send_report_email(
    scan_id: uuid.UUID, email: str, url: str
) -> None:
    from app.database import async_session
    from app.services.email import send_report
    from app.services.pdf import generate_report_pdf

    async with async_session() as session:
        pdf = await generate_report_pdf(str(scan_id), session)
    if pdf:
        await send_report(email, pdf, url)
