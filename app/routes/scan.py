import re
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_session
from app.models import Organization, Scan
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
    position = orchestrator.queue_position.get(scan.id)
    return ScanResponse.model_validate(scan, from_attributes=True).model_copy(
        update={"queue_position": position}
    )


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

    from app.main import get_orchestrator
    orchestrator = get_orchestrator()
    position = orchestrator.queue_position.get(scan.id)
    return ScanResultResponse.model_validate(scan, from_attributes=True).model_copy(
        update={"queue_position": position}
    )


@router.post("/scan/{scan_id}/email", status_code=202)
async def send_report_email(
    scan_id: uuid.UUID,
    request: EmailRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    scan = await session.get(Scan, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan niet gevonden")

    if scan.status == "error":
        raise HTTPException(status_code=400, detail="Scan is mislukt")

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
    import asyncio

    from app.database import async_session
    from app.services.email import send_report
    from app.services.pdf import generate_report_pdf

    # Wait for scan to complete (max 5 minutes)
    for _ in range(100):
        async with async_session() as session:
            scan = await session.get(Scan, scan_id)
        if not scan:
            return
        if scan.status == "done":
            break
        if scan.status == "error":
            return
        await asyncio.sleep(3)
    else:
        return  # Timeout — scan never completed

    async with async_session() as session:
        pdf = await generate_report_pdf(str(scan_id), session)
    if pdf:
        await send_report(email, pdf, url)


@router.get("/gemeenten/scores")
async def gemeente_scores(session: AsyncSession = Depends(get_session)):
    """Return SEAL scores for all gemeenten (used by the map page)."""
    from sqlalchemy import func, text

    result = await session.execute(
        text("""
            SELECT DISTINCT ON (o.name)
                o.name, o.provincie,
                ROUND((s.summary->>'weighted_average_level')::numeric, 2) AS score,
                (s.summary->>'total_hostnames')::int AS total_hostnames,
                (s.summary->>'third_party_hostnames')::int AS third_party_hostnames,
                s.summary->'level_distribution' AS level_distribution,
                s.summary->>'final_url' AS final_url
            FROM scans s
            JOIN organizations o ON s.organization_id = o.id
            WHERE s.status = 'done' AND o.category = 'gemeente'
            ORDER BY o.name, s.completed_at DESC
        """)
    )
    rows = result.mappings().all()
    return [dict(r) for r in rows]
