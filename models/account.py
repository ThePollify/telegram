from pydantic import Field

from models import BaseModel


class User(BaseModel):
    id: int
    username: str


class Auth(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class Token(BaseModel):
    id: int
    username: str
    token: str


class UpdateUsername(BaseModel):
    username: str = Field(min_length=1)


class UpdatePassword(BaseModel):
    password: str = Field(min_length=1)
