from fastapi import FastAPI

app = FastAPI(title="digital-twin-backend")


@app.get("/")
def health() -> dict:
    return {"service": "backend", "status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
