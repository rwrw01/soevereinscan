from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@router.get("/results/{scan_id}", response_class=HTMLResponse)
async def results_page(request: Request, scan_id: str):
    return templates.TemplateResponse("results.html", {"request": request, "scan_id": scan_id})
