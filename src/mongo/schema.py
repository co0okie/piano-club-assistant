from pydantic import BaseModel, RootModel
from typing import Literal

Weekday = Literal["M", "T", "W", "R", "F", "S", "U"]
Section = Literal["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "A", "B", "C", "D"]
Role = Literal["teacher", "student"]
WEEKDAYS = ("M", "T", "W", "R", "F", "S", "U")
SECTIONS = ("1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "A", "B", "C", "D")

class OneOnOneFormModel(BaseModel):
    student_id: str
    name: str
    role: Literal["teacher", "student"]
    availble_time: set[tuple[Weekday, Section]] = set()

Schedule = dict[Weekday, dict[Section, dict[Role, str] | None]]
class ScheduleModel(RootModel[Schedule]):
    pass