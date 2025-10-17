from pydantic import BaseModel, RootModel, Field, BeforeValidator
from typing import Literal, Annotated, Optional
from enum import Enum

PyObjectId = Annotated[str, BeforeValidator(str)]

Weekday = Literal["M", "T", "W", "R", "F", "S", "U"]
Section = Literal["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "A", "B", "C", "D"]
OneOnOneRole = Literal["teacher", "student"]
WEEKDAYS = ("M", "T", "W", "R", "F", "S", "U")
SECTIONS = ("1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "A", "B", "C", "D")

class OneOnOneFormModel(BaseModel):
    student_id: str
    name: str
    role: Literal["teacher", "student"]
    availble_time: set[tuple[Weekday, Section]] = set()

Schedule = dict[Weekday, dict[Section, dict[OneOnOneRole, str] | None]]
class ScheduleModel(RootModel[Schedule]):
    pass

class UserRole(str, Enum):
    GENERAL = "general" # 一般人、非社員
    MEMBER = "member" # 社員
    ADMIN = "admin" # 幹部

class UserModel(BaseModel):
    line_user_id: str = Field(..., pattern=r"^U[a-f0-9]{32}$")
    student_id: Optional[str] = ""
    name: Optional[str] = ""
    role: UserRole = Field(default=UserRole.GENERAL)