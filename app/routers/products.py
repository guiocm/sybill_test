from typing import List, Optional

from fastapi import Body, APIRouter, Security, status, HTTPException
from pydantic import BaseModel, Field

from app.auth import CurrentUserIdAdmin, get_current_authorized_user_id
from app.db import DBDependency
from app.utils import PyObjectId, parse_object_id


router = APIRouter(
    prefix="/products",
    tags=["products"],
)


class Product(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    name: str
    description: str | None = None
    price: float


class ProductUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    price: float | None = None


class ProductList(BaseModel):
    products: List[Product]


@router.post(
    "/",
    response_model=Product,
    status_code=status.HTTP_201_CREATED,
    response_model_by_alias=False,
)
async def create_product(
    db: DBDependency,
    current_user_id: CurrentUserIdAdmin,
    product: Product = Body(...),
):
    result = await db.products.insert_one(product.model_dump())
    return await db.products.find_one({"_id": result.inserted_id})


@router.get(
    "/",
    response_model=ProductList,
    response_model_by_alias=False,
)
async def list_products(db: DBDependency):
    cursor = db.products.find()
    return ProductList(products=await cursor.to_list(length=100))


@router.get(
    "/{product_id}",
    response_model=Product,
    response_model_by_alias=False,
)
async def get_product(db: DBDependency, product_id: str):
    parsed_product_id = parse_object_id(product_id)
    product = await db.products.find_one({"_id": parsed_product_id})
    if product:
        return product
    raise HTTPException(
        status_code=404, detail=f"Product with id '{product_id}' not found"
    )


@router.patch(
    "/{product_id}",
    response_model=Product,
    response_model_by_alias=False,
)
async def patch_product(
    db: DBDependency,
    current_user_id: CurrentUserIdAdmin,
    product_id: str,
    product: ProductUpdate = Body(...),
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


@router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_product(
    db: DBDependency, current_user_id: CurrentUserIdAdmin, product_id: str
):
    parsed_product_id = parse_object_id(product_id)
    result = await db.products.delete_one({"_id": parsed_product_id})
    if result.deleted_count == 1:
        return

    raise HTTPException(
        status_code=404, detail=f"Product with id '{product_id}' not found"
    )
