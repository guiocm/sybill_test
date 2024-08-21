from typing import Annotated, List, Optional

from bson import ObjectId
from fastapi import Body, APIRouter, Depends, Security, status, HTTPException
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError

from app.db import DBDependency
from app.utils import PyObjectId, parse_object_id
from app.auth import (
    CurrentUserIdAdmin,
    CurrentUserIdMe,
    PermissionData,
    get_current_authorized_user_id,
    get_current_permission_data,
    get_password_hash,
)


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


class CreateUserData(BaseModel):
    username: str
    password: str
    admin: bool | None


class User(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    username: str


class UserList(BaseModel):
    users: List[User]


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
    response_model=User,
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
    print([perm async for perm in db.permissions.find({"user_id": result.inserted_id})])
    return await db.users.find_one({"_id": result.inserted_id})


@router.get(
    "/",
    response_model=UserList,
    response_model_by_alias=False,
)
async def list_users(
    db: DBDependency,
    current_user_id: CurrentUserIdAdmin,
):
    cursor = db.users.find()
    return UserList(users=await cursor.to_list(length=100))


@router.delete("/")
async def clear_users(db: DBDependency):
    await db.users.delete_many({})


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
    current_user_id: CurrentUserIdAdmin,
):
    parsed_user_id = parse_object_id(user_id)
    return delete_user_from_db(db, parsed_user_id)


"""
@router.patch(
    "/{product_id}",
    response_model=Product,
    response_model_by_alias=False,
)
async def patch_product(
    db: DBDependency, product_id: str, product: ProductUpdate = Body(...)
):
    parsed_product_id = parse_object_id(product_id)
    product_dict = product.model_dump(by_alias=True)
    product_update = {
        field: product_dict[field]
        for field in product_dict
        if product_dict[field] is not None
    }

    if product_update:
        await db.products.find_one_and_update(
            {"_id": parsed_product_id},
            {"$set": product_update},
        )

    db_product = await db.products.find_one({"_id": parsed_product_id})
    if db_product:
        return db_product

    raise HTTPException(
        status_code=404, detail=f"Product with id '{product_id}' not found"
    )


"""
