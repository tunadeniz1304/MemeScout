from fastapi import FastAPI

app = FastAPI(
    title="MemeScout Annotation API",
    version="0.1.0",
)


@app.get("/api/v1/health")
def health():
    return {"durum": "calisiyor"}