from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.database import engine
from app.db import models

from app.api.endpoints.auth import router as auth_router
from app.api.endpoints.hospitals import router as hospitals_router
from app.api.endpoints.dispatch import router as dispatch_router
from app.api.endpoints.cases import router as cases_router
from app.api.endpoints.ai import router as ai_router
from app.api.endpoints import tracking

app = FastAPI(title="MediRoute API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

models.Base.metadata.create_all(bind=engine)

app.include_router(auth_router)
app.include_router(hospitals_router)
app.include_router(dispatch_router)
app.include_router(cases_router)
app.include_router(ai_router)
app.include_router(tracking.router)

@app.get("/")
def read_root():
    return {"status": "MediRoute API is running"}
