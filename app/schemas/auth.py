from pydantic import BaseModel, Field

from app.enums import PrivateQuestion


class SignupRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6, max_length=100)
    private_question: PrivateQuestion
    private_answer: str = Field(min_length=1, max_length=100)


class LoginRequest(BaseModel):
    username: str
    password: str
    private_answer: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    username: str
    private_question: PrivateQuestion

    class Config:
        from_attributes = True
