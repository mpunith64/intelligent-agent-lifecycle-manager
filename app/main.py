from fastapi import FastAPI
from app.api.agents import router as agent_router

app = FastAPI(
    title="Intelligent Agent Lifecycle Manager",
    description="CI/CD Agent Lifecycle and Session Management Platform",
    version="0.1.0"
)


@app.get("/")
async def root():
    return {
        "project": "Intelligent Agent Lifecycle Manager",
        "status": "running"
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


app.include_router(agent_router)