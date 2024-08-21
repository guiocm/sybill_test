from typing import Annotated

from fastapi import Depends
from motor import motor_asyncio


client = motor_asyncio.AsyncIOMotorClient("mongodb://admin:admin@localhost:27017")


def get_db():
    return client["main_database"]


DBDependency = Annotated[motor_asyncio.AsyncIOMotorDatabase, Depends(get_db)]
