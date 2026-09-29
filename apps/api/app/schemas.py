from pydantic import BaseModel


class RagDoc(BaseModel):
    location_id: str
    text: str


class RagQuery(BaseModel):
    text: str
    top_k: int = 5
