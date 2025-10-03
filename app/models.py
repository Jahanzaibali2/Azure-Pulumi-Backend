from __future__ import annotations
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class Node(BaseModel):
    id: str
    kind: str
    name: Optional[str] = None
    props: Dict[str, Any] = Field(default_factory=dict)

class Edge(BaseModel):
    from_: str = Field(alias="from")
    to: str
    intent: str = "notify"

class IR(BaseModel):
    project: str
    env: str
    location: Optional[str] = None
    region: Optional[str] = None
    nodes: List[Node] = Field(default_factory=list)
    edges: List[Edge] = Field(default_factory=list)

class AzureCreds(BaseModel):
    clientId: str
    clientSecret: str
    subscriptionId: str
    tenantId: str

class PreviewRequest(BaseModel):
    ir: IR
    creds: Optional[AzureCreds] = None

class UpRequest(BaseModel):
    ir: IR
    creds: Optional[AzureCreds] = None

class DestroyRequest(BaseModel):
    project: str
    env: str
