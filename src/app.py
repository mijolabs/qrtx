from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

_STATIC = Path(__file__).parent / "static"

app = FastAPI(title="qrtx")
app.mount("/static", StaticFiles(directory=_STATIC), name="static")


@app.get("/")
async def index():
    return FileResponse(_STATIC / "index.html", media_type="text/html")


@app.get("/send")
async def send():
    return FileResponse(_STATIC / "send.html", media_type="text/html")


@app.get("/receive")
async def receive():
    return FileResponse(_STATIC / "receive.html", media_type="text/html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
