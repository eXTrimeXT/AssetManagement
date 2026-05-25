from pydantic import BaseModel, ConfigDict
from typing import Literal

class SearchByAbbreviationResponse(BaseModel):
    entity_type: Literal["department", "division", "group"]
    id: int
    name: str
    abbreviation: str
    model_config = ConfigDict(from_attributes=True)