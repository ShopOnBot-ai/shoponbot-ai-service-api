from fastapi import FastAPI

from api.v1 import router as v1_router


app = FastAPI(
    title="E-commerce AI Service",
    version="1.0.0"
)

app.include_router(
    v1_router.router,
    prefix="/api/v1"
)