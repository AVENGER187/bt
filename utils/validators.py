from pydantic import BaseModel, Field, field_validator
from database.schemas import GenderEnum

class CreateProfileRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    age: int | None = None
    gender: GenderEnum | None = None
    profession: str | None = None
    bio: str | None = None
    is_actor: bool = False
    profile_photo_url: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    years_of_experience: int | None = None
    previous_projects: str | None = None
    portfolio_url: str | None = None
    skill_ids: list[int] = []
    
    @field_validator('age', 'gender', 'profile_photo_url')
    def check_actor_requirements(cls, v, info):
        values = info.data
        if values.get('is_actor') and v is None:
            raise ValueError(f"{info.field_name} is required for actors")
        return v