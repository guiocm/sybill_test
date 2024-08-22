from typing import Annotated

from bson import ObjectId, errors
from fastapi import HTTPException
from pydantic import BeforeValidator


PyObjectId = Annotated[str, BeforeValidator(str)]


def parse_object_id(id_str):
    try:
        return ObjectId(id_str)
    except errors.InvalidId:
        raise HTTPException(status_code=400, detail=f"Invalid ObjectId {id_str}")


def pagination_parameters(skip: int = 0, limit: int = 100):
    return {"skip": skip, "limit": limit}
