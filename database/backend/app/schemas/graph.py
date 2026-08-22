import uuid
from typing import List
from pydantic import BaseModel, Field, ConfigDict


class GraphNode(BaseModel):
    id: str
    label: str
    status: str
    depth: int
    x: float
    y: float


class GraphEdge(BaseModel):
    from_: str = Field(alias="from")
    to: str
    
    model_config = ConfigDict(populate_by_name=True)


class GraphResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]
