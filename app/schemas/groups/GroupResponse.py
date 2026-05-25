from pydantic import BaseModel, Field

class GroupResponse(BaseModel):
    id: int
    name: str
    abbreviation: str
    division_id: int

    class Config:
        from_attributes = True

class GroupShortResponse(BaseModel):
    id: int
    name: str
    abbreviation: str

    class Config:
        from_attributes = True