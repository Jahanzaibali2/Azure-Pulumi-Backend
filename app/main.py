
from __future__ import annotations

import os, shutil
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.models import IR, UpRequest, PreviewRequest, DestroyRequest, AzureCreds
from app.services.utils import get_allowed_origins
from app.services.pulumi_engine import PulumiEngine, init_pulumi_env

load_dotenv()
init_pulumi_env()  # <-- add this line


app = FastAPI(title="Azure IR → Pulumi Backend", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _export_azure_creds(creds: Optional[AzureCreds]):
    if not creds:
        return
    os.environ["ARM_CLIENT_ID"] = creds.clientId
    os.environ["ARM_CLIENT_SECRET"] = creds.clientSecret
    os.environ["ARM_TENANT_ID"] = creds.tenantId
    os.environ["ARM_SUBSCRIPTION_ID"] = creds.subscriptionId

@app.get("/health")
def health():
    return {
        "status": "ok",
        "locationDefault": os.getenv("AZURE_LOCATION", "westeurope"),
        "pulumiOnPath": bool(shutil.which("pulumi")),
        "backend": os.getenv("PULUMI_BACKEND_URL", ""),
    }

@app.post("/preview")
def preview(req: PreviewRequest):
    try:
        _export_azure_creds(req.creds)
        return PulumiEngine.preview(req.ir.model_dump())
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/up")
def up(req: UpRequest):
    try:
        _export_azure_creds(req.creds)
        return PulumiEngine.up(req.ir.model_dump())
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/destroy")
def destroy(req: DestroyRequest):
    try:
        return PulumiEngine.destroy(req.project, req.env)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
