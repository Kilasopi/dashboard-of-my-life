from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.system_health import router as system_health_router

app = FastAPI(title="Dashboard of My Life API")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://localhost:\d+",
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(system_health_router)


@app.get("/")
def root():
    return {"message": "Dashboard of My Life API is running"}