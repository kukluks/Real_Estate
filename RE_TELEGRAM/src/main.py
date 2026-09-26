from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.api.routers.notify import router

app = FastAPI()
app.include_router(router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.exception_handler(Exception)
async def exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"message": "An internal server error occurred."})
