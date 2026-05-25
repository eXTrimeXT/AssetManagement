from pydantic import BaseModel, Field

class DivisionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    abbreviation: str = Field(..., min_length=1, max_length=50)
    department_id: int = Field(..., gt=0)

    class Config:
        from_attributes = True