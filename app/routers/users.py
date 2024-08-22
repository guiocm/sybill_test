from typing import Annotated, List, Optional

from bson import ObjectId
from fastapi import Body, APIRouter, Depends, Security, status, HTTPException
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError

from app.db import DBDependency
from app.utils import PyObjectId, parse_object_id, pagination_parameters
from app.auth import (
    CurrentUserIdAdmin,
    CurrentUserIdMe,
    PermissionData,
    get_current_authorized_user_id,
    get_current_permission_data,
    get_password_hash,
)
from app.routers.carts import create_cart_in_db, Cart


BASE_PERMISSIONS = [
    "shopper",
    "me",
]

ADMIN_PERMISSIONS = [
    "admin",
]


router = APIRouter(
    prefix="/users",
    tags=["users"],
)


class User(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    username: str
    name: str | None = None
    address: str | None = None


class CreateUserData(User):
    password: str
    admin: bool | None = None


class UpdateUserData(BaseModel):
    name: str | None = None
    address: str | None = None
    password: str | None = None


class UserList(BaseModel):
    skip: int
    limit: int
    total_results: int
    users: List[User]


class CreateUserResponse(BaseModel):
    user: User
    cart: Cart


async def create_permissions(db, permissions):
    return db.permissions.insert_many(permissions)


def create_base_permissions(db, user_id: ObjectId):
    return create_permissions(
        db, [{"user_id": user_id, "scope": scope} for scope in BASE_PERMISSIONS]
    )


def create_admin_permissions(db, user_id: ObjectId):
    return create_permissions(
        db, [{"user_id": user_id, "scope": scope} for scope in ADMIN_PERMISSIONS]
    )


@router.post(
    "/",
    response_model=CreateUserResponse,
    status_code=status.HTTP_201_CREATED,
    response_model_by_alias=False,
)
async def create_user(db: DBDependency, user_data: CreateUserData = Body(...)):
    try:
        result = await db.users.insert_one(
            {
                "username": user_data.username,
                "hashed_password": get_password_hash(user_data.password),
            }
        )
    except DuplicateKeyError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="username already exists"
        )
    await create_base_permissions(db, result.inserted_id)
    if user_data.admin:
        await create_admin_permissions(db, result.inserted_id)
    user = await db.users.find_one({"_id": result.inserted_id})
    cart = await create_cart_in_db(db, result.inserted_id)
    return {"user": user, "cart": cart}


@router.get(
    "/",
    response_model=UserList,
    response_model_by_alias=False,
)
async def list_users(
    db: DBDependency,
    current_user_id: CurrentUserIdAdmin,
    pagination: Annotated[dict, Depends(pagination_parameters)],
):
    total_results = await db.users.count_documents({})
    cursor = db.users.find({}).skip(pagination["skip"]).limit(pagination["limit"])
    return {
        **pagination,
        "total_results": total_results,
        "users": await cursor.to_list(length=pagination["limit"]),
    }


async def get_user_from_db(db, user_id: ObjectId):
    user = await db.users.find_one({"_id": user_id})
    if user:
        return user
    raise HTTPException(
        status_code=404, detail=f"user with id '{str(user_id)}' not found"
    )


@router.get(
    "/me",
    response_model=User,
    response_model_by_alias=False,
)
async def get_current_user(
    db: DBDependency,
    user_id: CurrentUserIdMe,
):
    return await get_user_from_db(db, user_id)


@router.get(
    "/{user_id}",
    response_model=User,
    response_model_by_alias=False,
)
async def get_user(
    db: DBDependency,
    user_id: str,
    current_user_id: CurrentUserIdAdmin,
):
    parsed_user_id = parse_object_id(user_id)
    return await get_user_from_db(db, parsed_user_id)


async def delete_user_from_db(db, user_id: ObjectId):
    cart_result = await db.carts.delete_many({"user_id": user_id})
    result = await db.users.delete_one({"_id": user_id})
    if result.deleted_count == 1:
        return

    raise HTTPException(
        status_code=404, detail=f"user with id '{str(user_id)}' not found"
    )


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_current_user(
    db: DBDependency,
    user_id: CurrentUserIdMe,
):
    return await delete_user_from_db(db, user_id)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_user(
    db: DBDependency,
    user_id: str,
    _: CurrentUserIdAdmin,
):
    parsed_user_id = parse_object_id(user_id)
    return await delete_user_from_db(db, parsed_user_id)


async def update_user_in_db(db, user_id: ObjectId, update_user_data: UpdateUserData):
    user_dict = update_user_data.model_dump(by_alias=True)
    user_update = {
        field: user_dict[field] for field in user_dict if user_dict[field] is not None
    }

    if "password" in user_update:
        password = user_update.pop("password")
        user_update["hashed_password"] = get_password_hash(password)

    if user_update:
        await db.users.find_one_and_update(
            {"_id": user_id},
            {"$set": user_update},
        )

    if db_user := await db.users.find_one({"_id": user_id}):
        return db_user

    raise HTTPException(
        status_code=404, detail=f"user with id '{str(user_id)}' not found"
    )


@router.patch(
    "/me",
    response_model=User,
    response_model_by_alias=False,
)
async def patch_user(
    db: DBDependency,
    user_id: CurrentUserIdMe,
    update_user_data: UpdateUserData = Body(...),
):
    return await update_user_in_db(db, user_id, update_user_data)


@router.patch(
    "/{user_id}",
    response_model=User,
    response_model_by_alias=False,
)
async def patch_user(
    db: DBDependency,
    user_id: str,
    _: CurrentUserIdAdmin,
    update_user_data: UpdateUserData = Body(...),
):
    parsed_user_id = parse_object_id(user_id)
    return await update_user_in_db(db, parsed_user_id, update_user_data)
