from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ItemsFoundParams(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title_id: str | None = Field(default=None, alias="titleId")
    name_id: str | None = Field(default=None, alias="nameId")
    title_type: str | None = Field(default=None, alias="titleType")
    genre: str | None = None
    rating_range_from: float | None = Field(
        default=None, alias="ratingRangeFrom", ge=1.0, le=10.0
    )
    rating_range_to: float | None = Field(
        default=None, alias="ratingRangeTo", ge=1.0, le=10.0
    )
    release_year_from: int | None = Field(default=None, alias="releaseYearFrom")
    release_year_to: int | None = Field(default=None, alias="releaseYearTo")
    top_rated: bool = Field(default=False, alias="topRated")
    most_popular: bool = Field(default=False, alias="mostPopular")

    @model_validator(mode="after")
    def _validate_ranges(self) -> ItemsFoundParams:
        if (
            self.rating_range_from is not None
            and self.rating_range_to is not None
            and self.rating_range_from > self.rating_range_to
        ):
            raise ValueError("ratingRangeFrom must be less than or equal to ratingRangeTo")

        if (
            self.release_year_from is not None
            and self.release_year_to is not None
            and self.release_year_from > self.release_year_to
        ):
            raise ValueError("releaseYearFrom must be less than or equal to releaseYearTo")

        return self


class ItemsFoundResponse(BaseModel):
    totalTitles: int
    totalPersons: int
