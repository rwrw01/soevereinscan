from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


def _context(request: Request, **kwargs) -> dict:
    """Build template context with base path for all URL references."""
    base = request.scope.get("root_path", "")
    return {"request": request, "base": base, **kwargs}


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", _context(request))


@router.get("/results/{scan_id}", response_class=HTMLResponse)
async def results_page(request: Request, scan_id: str):
    return templates.TemplateResponse("results.html", _context(request, scan_id=scan_id))
