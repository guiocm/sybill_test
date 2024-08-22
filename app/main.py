from typing import Annotated
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.auth import Token, create_access_token, verify_password
from app.db import DBDependency, ensure_indexes
from app.routers import products, users, carts
from app.utils import RESPONSE_401_UNAUTHORIZED


@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_indexes()
    yield


app = FastAPI(lifespan=lifespan)

app.include_router(products.router)
app.include_router(users.router)
app.include_router(carts.router, prefix="/users/me")


@app.post("/token", responses=RESPONSE_401_UNAUTHORIZED)
async def login_for_access_token(
    db: DBDependency,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> Token:
    user = await db.users.find_one({"username": form_data.username})
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user["username"]})
    return Token(access_token=access_token, token_type="bearer")
