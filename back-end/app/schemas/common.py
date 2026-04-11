from pydantic import BaseModel, Field


class CommonListQueryParams(BaseModel):
    skip: int = Field(default=0, description="Number of items to skip")
    limit: int = Field(default=100, lt=1000, description="Maximum number of items to return")
