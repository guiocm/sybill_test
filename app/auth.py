from datetime import datetime, timedelta, timezone
from typing import Annotated, List, Set
from bson import ObjectId
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import OAuth2PasswordBearer, SecurityScopes
import jwt
from passlib.context import CryptContext
from pydantic import BaseModel, ConfigDict

from app.db import DBDependency

SECRET_KEY = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


class Token(BaseModel):
    access_token: str
    token_type: str


class PermissionData(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    user_id: ObjectId
    permissions: Set[str]


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_user_permissions(db, username: str) -> PermissionData:
    user = await db.users.find_one({"username": username})
    if not user:
        return None
    permissions = [
        permission["scope"]
        async for permission in db.permissions.find({"user_id": user["_id"]})
    ]
    return PermissionData(user_id=user["_id"], permissions=permissions)


async def get_current_permission_data(
    db: DBDependency, token: Annotated[str, Depends(oauth2_scheme)]
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except jwt.InvalidTokenError:
        raise credentials_exception
    user_permissions = await get_user_permissions(db, username=username)
    if user_permissions is None:
        raise credentials_exception
    return user_permissions


async def get_current_authorized_user_id(
    security_scopes: SecurityScopes,
    permission_data: Annotated[PermissionData, Depends(get_current_permission_data)],
):
    for scope in security_scopes.scopes:
        if scope not in permission_data.permissions:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User doesn't have necessary permissions",
            )
    return permission_data.user_id


CurrentUserIdAdmin = Annotated[
    ObjectId, Security(get_current_authorized_user_id, scopes=["admin"])
]

CurrentUserIdMe = Annotated[
    ObjectId, Security(get_current_authorized_user_id, scopes=["me"])
]
CurrentUserIdShopper = Annotated[
    ObjectId, Security(get_current_authorized_user_id, scopes=["shopper"])
]
