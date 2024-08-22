from typing import List, Optional

from bson import ObjectId
from fastapi import Body, APIRouter, Security, status, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.auth import CurrentUserIdAdmin, CurrentUserIdMe, get_current_authorized_user_id
from app.db import DBDependency
from app.routers.products import get_product_from_db
from app.utils import (
    RESPONSE_401_UNAUTHORIZED,
    RESPONSE_404_NOT_FOUND,
    PyObjectId,
    parse_object_id,
)


router = APIRouter(
    prefix="/carts",
    tags=["carts"],
)


class Cart(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: PyObjectId
    items: List[PyObjectId]


class AddToCartData(BaseModel):
    product_id: PyObjectId


async def create_cart_in_db(db, user_id: ObjectId):
    result = await db.carts.insert_one({"user_id": user_id, "items": []})
    return await db.carts.find_one({"_id": result.inserted_id})


async def get_cart_from_db(db, user_id: ObjectId, cart_id: ObjectId):
    if cart := await db.carts.find_one({"_id": cart_id, "user_id": user_id}):
        return cart
    raise HTTPException(
        status_code=404,
        detail=f"Cart with id {str(cart_id)} not found for user {str(user_id)}",
    )


@router.post(
    "/",
    response_model=Cart,
    status_code=status.HTTP_201_CREATED,
    response_model_by_alias=False,
    responses=RESPONSE_401_UNAUTHORIZED,
)
async def create_cart(db: DBDependency, current_user_id: CurrentUserIdMe):
    return await create_cart_in_db(db, current_user_id)


@router.get(
    "/{cart_id}",
    response_model=Cart,
    response_model_by_alias=False,
    responses={**RESPONSE_401_UNAUTHORIZED, **RESPONSE_404_NOT_FOUND},
)
async def get_cart(db: DBDependency, current_user_id: CurrentUserIdMe, cart_id: str):
    parsed_cart_id = parse_object_id(cart_id)
    return await get_cart_from_db(db, current_user_id, parsed_cart_id)


@router.post(
    "/{cart_id}/items",
    response_model=Cart,
    response_model_by_alias=False,
    responses={**RESPONSE_401_UNAUTHORIZED, **RESPONSE_404_NOT_FOUND},
)
async def add_item_to_cart(
    db: DBDependency,
    current_user_id: CurrentUserIdMe,
    cart_id: str,
    add_data: AddToCartData = Body(...),
):
    parsed_cart_id = parse_object_id(cart_id)
    parsed_product_id = parse_object_id(add_data.product_id)
    product = await get_product_from_db(db, parsed_product_id)
    await db.carts.update_one(
        {"_id": parsed_cart_id, "user_id": current_user_id},
        {"$push": {"items": parsed_product_id}},
    )
    return await get_cart_from_db(db, current_user_id, parsed_cart_id)


@router.delete(
    "/{cart_id}/items/{product_id}",
    response_model=Cart,
    response_model_by_alias=False,
    responses={**RESPONSE_401_UNAUTHORIZED, **RESPONSE_404_NOT_FOUND},
)
async def remove_item_from_cart(
    db: DBDependency,
    current_user_id: CurrentUserIdMe,
    cart_id: str,
    product_id: str,
):
    parsed_cart_id = parse_object_id(cart_id)
    parsed_product_id = parse_object_id(product_id)
    cart = await get_cart_from_db(db, current_user_id, parsed_cart_id)
    if parsed_product_id not in cart["items"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No item with product id {product_id} in cart",
        )
    await db.carts.update_one(
        {"_id": parsed_cart_id, "user_id": current_user_id},
        {"$pull": {"items": parsed_product_id}},
    )
    return await get_cart_from_db(db, current_user_id, parsed_cart_id)


@router.delete(
    "/{cart_id}/items",
    response_model=Cart,
    response_model_by_alias=False,
    responses={**RESPONSE_401_UNAUTHORIZED, **RESPONSE_404_NOT_FOUND},
)
async def clear_cart(
    db: DBDependency,
    current_user_id: CurrentUserIdMe,
    cart_id: str,
):
    parsed_cart_id = parse_object_id(cart_id)
    await db.carts.update_one(
        {"_id": parsed_cart_id, "user_id": current_user_id},
        {"$set": {"items": []}},
    )
    return await get_cart_from_db(db, current_user_id, parsed_cart_id)


@router.delete(
    "/{cart_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={**RESPONSE_401_UNAUTHORIZED, **RESPONSE_404_NOT_FOUND},
)
async def delete_cart(
    db: DBDependency,
    current_user_id: CurrentUserIdMe,
    cart_id: str,
):
    parsed_cart_id = parse_object_id(cart_id)
    result = await db.carts.delete_one(
        {"_id": parsed_cart_id, "user_id": current_user_id},
    )
    if result.deleted_count == 1:
        return

    raise HTTPException(
        status_code=404,
        detail=f"Cart with id {str(cart_id)} not found for user {str(current_user_id)}",
    )
