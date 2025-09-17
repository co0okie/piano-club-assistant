from fastapi import FastAPI, HTTPException
from pymongo import MongoClient
import os
from pydantic import BaseModel, RootModel
from typing import Literal
import one_on_one_teaching
from rich import print

client = MongoClient(f"mongodb://{os.getenv('MONGO_INITDB_ROOT_USERNAME')}:{os.getenv('MONGO_INITDB_ROOT_PASSWORD')}@mongo:27017")
db = client["piano-club"]
one_on_one_enroll_collection = db["one-on-one-teaching-enrollments"]
one_on_one_schedule_collection = db["one-on-one-teaching-schedule"]

Weekday = Literal["M", "T", "W", "R", "F", "S", "U"]
Section = Literal["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "A", "B", "C", "D"]
Role = Literal["teacher", "student"]
WEEKDAYS = ("M", "T", "W", "R", "F", "S", "U")
SECTIONS = ("1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "A", "B", "C", "D")

class OneOnOneForm(BaseModel):
    student_id: str
    name: str
    role: Literal["teacher", "student"]
    availble_time: set[tuple[Weekday, Section]] = set()

Schedule = dict[Weekday, dict[Section, dict[Role, str] | None]]
class ScheduleModel(RootModel[Schedule]):
    pass

app = FastAPI(
    root_path="/api"
)

@app.put("/one-on-one")
def add_submission(form: OneOnOneForm):
    one_on_one_enroll_collection.replace_one(
        {"student_id": form.student_id},
        form.model_dump(mode="json"),
        upsert=True
    )
    return "Submitted successfully"

@app.get("/one-on-one", response_model=list[OneOnOneForm])
def list_submissions():
    return [
        OneOnOneForm.model_validate(form)
        for form in one_on_one_enroll_collection.find({}, {"_id": 0})
    ]

@app.get("/one-on-one/{student_id}", response_model=OneOnOneForm)
def get_submission(student_id: str):
    doc = one_on_one_enroll_collection.find_one({"student_id": student_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Record not found")
    return doc

@app.delete("/one-on-one/{student_id}")
def delete_submission(student_id: str):
    result = one_on_one_enroll_collection.delete_one({"student_id": student_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    return "Deleted successfully"

@app.put("/one-on-one-schedule", response_model=ScheduleModel)
def update_schedule() -> ScheduleModel:
    forms = list_submissions()
    result = one_on_one_teaching.schedule(
        students=[
            one_on_one_teaching.Student(
                available_time=form.availble_time,
                obj=form
            )
            for form in forms if form.role == "student"
        ],
        teachers=[
            one_on_one_teaching.Teacher(
                available_time=form.availble_time,
                max_students=1,
                obj=form
            )
            for form in forms if form.role == "teacher"
        ]
    )
    print([f"{t.section}: {t.teacher.name} teach {t.student.name}" for t in result])
    
    schedule: Schedule = {
        weekday: {section: None for section in SECTIONS} for weekday in WEEKDAYS
    }
    for t in result:
        schedule[t.section[0]][t.section[1]] = {
            "teacher": t.teacher.name,
            "student": t.student.name
        }
    schedule_model = ScheduleModel.model_validate(schedule)

    update_result = one_on_one_schedule_collection.replace_one(
        {},
        schedule_model.model_dump(mode="json"),
        upsert=True
    )
    print(update_result)
    return schedule_model

@app.get("/one-on-one-schedule", response_model=ScheduleModel)
def get_schedule() -> ScheduleModel:
    schedule = one_on_one_schedule_collection.find_one({}, {"_id": 0})
    if not schedule:
        return update_schedule()
    return ScheduleModel.model_validate(schedule)