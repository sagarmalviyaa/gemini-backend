from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
from datetime import datetime
from app.config import settings
from app.database import engine, Base
from app.routers import auth, user, chatroom, subscription

# ==== Enhanced Logging Setup ====
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger("gemini-backend")  # Use a custom app logger name

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up Gemini Backend Clone")
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables checked/created")
    except Exception as e:
        logger.error(f"Error creating DB tables: {e}")
        raise
    yield
    # Shutdown
    logger.info("Shutting down Gemini Backend Clone")

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="A Gemini-style backend system with AI conversations and subscription management",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(user.router)
app.include_router(chatroom.router)
app.include_router(subscription.router)

@app.get("/")
async def root():
    """Root endpoint"""
    logger.info("GET / (root)")
    return {
        "message": "Welcome to Gemini Backend Clone",
        "version": settings.app_version,
        "docs": "/docs"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    logger.debug("GET /health")
    return {"status": "healthy"}

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.warning(f"HTTPException {exc.status_code} @ {request.url}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "status_code": exc.status_code,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception for {request.url} ({request.method}): {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "status_code": 500,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    )

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Uvicorn server (main)...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
