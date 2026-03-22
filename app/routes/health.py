from fastapi import APIRouter

router = APIRouter()


@router.get("/healthz")
async def liveness():
    return {"status": "ok"}


@router.get("/readyz")
async def readiness():
    return {"status": "ok"}
