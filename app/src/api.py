import os

import uvicorn
from fastapi import FastAPI

from routers import auth, balance, users, predictions, history, internal


app = FastAPI()

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(balance.router)
app.include_router(predictions.router)
app.include_router(history.router)
app.include_router(internal.router)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "ML service is running"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# -------------------------------------------------------------------------
if __name__ == "__main__":
    host = os.getenv("APP_HOST", "0.0.0.0")
    port = int(os.getenv("APP_PORT", "8000"))

    uvicorn.run(app, host=host, port=port)
