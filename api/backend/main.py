from os import getenv

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from uvicorn import run

from app.lifespan import build_lifespan
from app.routes import build_router
from infrastructure import logging as logging_config
from infrastructure.database import engine, metadata


logger = logging_config.init()
app = FastAPI(lifespan=build_lifespan(logger))

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4200",
        "http://158.160.17.229:4200",
        "http://0.0.0.0:4200",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(build_router(logger))


if __name__ == "__main__":
    metadata.create_all(engine)
    run(
        "main:app",
        host="0.0.0.0",
        port=int(getenv("PORT", "8901")),
        reload=True,
    )
