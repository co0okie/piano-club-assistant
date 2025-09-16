from fastapi import FastAPI, HTTPException
from pymongo import MongoClient
from bson import ObjectId
import os
from pydantic import BaseModel
from typing import Literal


client = MongoClient(f"mongodb://{os.getenv('MONGO_INITDB_ROOT_USERNAME')}:{os.getenv('MONGO_INITDB_ROOT_PASSWORD')}@mongo:27017")
db = client["piano_club"]
one_on_one_collection = db["one-on-one_teaching_enrollments"]


class OneOnOneForm(BaseModel):
    conversation_id: str
    name: str
    role: Literal["teacher", "student"]
    availble_time: set[tuple[
        Literal["M", "T", "W", "R", "F", "S", "U"],
        Literal["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "A", "B", "C", "D"]
    ]]


app = FastAPI(
    root_path="/api"
)


@app.post("/one-on-one")
def add_submission(form: OneOnOneForm):
    result = one_on_one_collection.replace_one(
        {"conversation_id": form.conversation_id},
        form.model_dump(mode="json"),
        upsert=True
    )
    return True

@app.get("/one-on-one")
def list_submissions():
    return list(one_on_one_collection.find({}, {"_id": 0}))

@app.get("/one-on-one/{conversation_id}")
def get_submission(conversation_id: str):
    doc = one_on_one_collection.find_one({"conversation_id": conversation_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Record not found")
    return doc

@app.delete("/one-on-one/{conversation_id}")
def delete_submission(conversation_id: str):
    result = one_on_one_collection.delete_one({"conversation_id": conversation_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"deleted_id": conversation_id}
