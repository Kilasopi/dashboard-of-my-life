from fastapi import FastAPI

app = FastAPI(title="Dashboard of My Life API")


@app.get("/")
def root():
    return {"message": "Dashboard of My Life API is running"}