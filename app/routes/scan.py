import uuid
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
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
