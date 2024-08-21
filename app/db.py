from typing import Annotated

from fastapi import Depends
from motor import motor_asyncio
import pymongo


client = motor_asyncio.AsyncIOMotorClient("mongodb://admin:admin@localhost:27017")


def get_db():
    return client["main_database"]


async def ensure_indexes():
    db = get_db()
    db.users.create_index([("username", pymongo.ASCENDING)], unique=True)


DBDependency = Annotated[motor_asyncio.AsyncIOMotorDatabase, Depends(get_db)]
