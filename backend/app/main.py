from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.routes import ingestion, encoding, eda, balancing

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Setup CORS for the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingestion.router, prefix=f"{settings.API_V1_STR}/datasets", tags=["datasets"])
app.include_router(encoding.router, prefix=f"{settings.API_V1_STR}/datasets", tags=["encoding"])
app.include_router(eda.router, prefix=f"{settings.API_V1_STR}/datasets", tags=["eda"])
app.include_router(balancing.router, prefix=f"{settings.API_V1_STR}/datasets", tags=["balancing"])

@app.get("/health")
def health_check():
    return {"status": "ok"}
