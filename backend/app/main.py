from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import paper_accounts_router
from app.core.config import get_settings
from app.services.paper_accounts import PaperAccountService


settings = get_settings()

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.paper_account_service = PaperAccountService()
app.include_router(paper_accounts_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.environment,
    }