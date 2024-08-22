from enum import Enum
from typing import Annotated, List, Optional

from bson import ObjectId
from fastapi import Body, APIRouter, Depends, Security, status, HTTPException
from pydantic import BaseModel, Field

from app.auth import CurrentUserIdAdmin, get_current_authorized_user_id
from app.db import DBDependency
from app.utils import PyObjectId, pagination_parameters, parse_object_id


router = APIRouter(
    prefix="/products",
    tags=["products"],
)


class SortingFields(Enum):
    name = "name"
    price = "price"


class SortingOrder(Enum):
    ascending = "asc"
    descending = "desc"


class PriceFilterOp(Enum):
    gt = "gt"
    lt = "lt"
    gte = "gte"
    lte = "lte"


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
    skip: int
    limit: int
    total_results: int
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


def build_query(price_filter_op: PriceFilterOp, price_filter_value: float):
    return {"price": {f"${price_filter_op.value}": price_filter_value}}


@router.get(
    "/",
    response_model=ProductList,
    response_model_by_alias=False,
)
async def list_products(
    db: DBDependency,
    pagination: Annotated[dict, Depends(pagination_parameters)],
    sort: SortingFields | None = None,
    order: SortingOrder | None = None,
    price_filter_op: PriceFilterOp | None = None,
    price_filter_value: float | None = None,
):
    if (sort or order) and not (sort and order):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid combination of sort and order parameters",
        )
    if (price_filter_op or price_filter_value) and not (
        price_filter_op and price_filter_value
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid combination of price_filter_op and price_filter_value parameters",
        )
    if price_filter_op and price_filter_value:
        query = build_query(price_filter_op, price_filter_value)
    else:
        query = {}
    total_results = await db.products.count_documents(query)
    cursor = db.products.find(query)
    if sort and order:
        cursor = cursor.sort({sort.value: 1 if order == SortingOrder.ascending else -1})
    cursor = cursor.skip(pagination["skip"]).limit(pagination["limit"])
    return {
        **pagination,
        "total_results": total_results,
        "products": await cursor.to_list(length=100),
    }


async def get_product_from_db(db, product_id: ObjectId):
    if product := await db.products.find_one({"_id": product_id}):
        return product
    raise HTTPException(
        status_code=404, detail=f"Product with id '{str(product_id)}' not found"
    )


@router.get(
    "/{product_id}",
    response_model=Product,
    response_model_by_alias=False,
)
async def get_product(db: DBDependency, product_id: str):
    parsed_product_id = parse_object_id(product_id)
    return await get_product_from_db(db, parsed_product_id)


@router.patch(
    "/{product_id}",
    response_model=Product,
    response_model_by_alias=False,
)
async def patch_product(
    db: DBDependency,
    _: CurrentUserIdAdmin,
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

    if db_product := await db.products.find_one({"_id": parsed_product_id}):
        return db_product

    raise HTTPException(
        status_code=404, detail=f"Product with id '{product_id}' not found"
    )


@router.put(
    "/{product_id}",
    response_model=Product,
    response_model_by_alias=False,
)
async def put_product(
    db: DBDependency,
    _: CurrentUserIdAdmin,
    product_id: str,
    product: Product = Body(...),
):
    parsed_product_id = parse_object_id(product_id)
    product_dict = product.model_dump(by_alias=True)
    product_dict["_id"] = parsed_product_id

    await db.products.find_one_and_update(
        {"_id": parsed_product_id},
        {"$set": product_dict},
    )

    if db_product := await db.products.find_one({"_id": parsed_product_id}):
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
