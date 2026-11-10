"""
EduEval AI — FastAPI Application Entry Point

API key configuration notice:
  - Set OPENAI_API_KEY in Backend/.env
  - Never hardcode the key in source files
  - Never commit .env to version control
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import engine, Base
from app.core.security import get_password_hash
from app.api.routes import auth, admin, faculty, student

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)
settings = get_settings()


def create_tables() -> None:
    """Create all database tables."""
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created/verified")


def create_default_admin() -> None:
    """Create the default admin account if it doesn't exist."""
    from app.core.database import SessionLocal
    from app.models.models import User, UserRole

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == "admin@edueval.ai").first()
        if not existing:
            admin_user = User(
                email="admin@edueval.ai",
                full_name="System Administrator",
                hashed_password=get_password_hash("Admin@123"),
                role=UserRole.admin,
                is_active=True,
            )
            db.add(admin_user)
            db.commit()
            logger.info("✅ Default admin created: admin@edueval.ai / Admin@123")
        else:
            logger.info("Admin account already exists")
    finally:
        db.close()


def print_startup_banner() -> None:
    logger.info("=" * 60)
    logger.info("  EduEval AI — Academic Evaluation Platform")
    logger.info("=" * 60)
    if settings.openai_configured:
        logger.info("  ✅ AI evaluation service: Configured")
    else:
        logger.warning("  ⚠️  OpenAI API key NOT configured")
        logger.warning("  → Open Backend/.env and set: OPENAI_API_KEY=<your_key>")
        logger.warning("  → Restart the backend server after saving")
        logger.warning("  → AI evaluation features will be unavailable until configured")
    logger.info("  📖 Docs: http://localhost:8000/docs")
    logger.info("=" * 60)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Startup
    create_tables()
    create_default_admin()
    print_startup_banner()
    yield
    # Shutdown
    logger.info("EduEval AI shutting down")


app = FastAPI(
    title="EduEval AI",
    description="AI-Powered Academic Evaluation Platform",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(faculty.router)
app.include_router(student.router)


@app.get("/")
def root() -> dict[str, str | bool]:
    return {
        "app": "EduEval AI",
        "version": "1.0.0",
        "status": "running",
        "openai_configured": settings.openai_configured,
        "docs": "/docs",
    }


@app.get("/health")
def health() -> dict[str, str | bool | None]:
    return {
        "status": "healthy",
        "openai_ready": settings.openai_configured,
    }
