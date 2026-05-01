from fastapi import FastAPI
from app.webhook import router

app = FastAPI(title="PR Reviewer")
app.include_router(router)

@app.get("/")
def health():
    return {"status": "alive"}