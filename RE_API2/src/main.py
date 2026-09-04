import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.api.exceptions import AppError
from src.api.routers.property import router

app = FastAPI()

app.include_router(router)

@app.get("/health")
async def healthcheck():
    return {"status": "ok"}

@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=getattr(exc, "status_code", 400),
        content={"message": str(exc)},
    )

@app.exception_handler(Exception)
async def exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"message": "An internal server error occurred."},
    )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
