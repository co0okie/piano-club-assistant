from pydantic import BaseModel, RootModel, Field, BeforeValidator
from typing import Literal, Annotated, Optional
from enum import Enum

Weekday = Literal["M", "T", "W", "R", "F", "S", "U"]
ClassPeriod = Literal["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "A", "B", "C", "D"]
WEEKDAYS = ("M", "T", "W", "R", "F", "S", "U")
CLASS_PERIOD = ("1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "A", "B", "C", "D")

line_user_id_field = Field(..., pattern=r"^U[a-f0-9]{32}$")

class OneOnOneRole(str, Enum):
    TEACHER = "teacher"
    STUDENT = "student"

class OneOnOneFormModel(BaseModel):
    line_user_id: str = line_user_id_field
    role: OneOnOneRole
    availble_time: set[tuple[Weekday, ClassPeriod]] = set()

Schedule = dict[Weekday, dict[ClassPeriod, dict[OneOnOneRole, str] | None]]
class ScheduleModel(RootModel[Schedule]):
    pass

class UserRole(str, Enum):
    GENERAL = "general" # 一般人、非社員
    MEMBER = "member" # 社員
    ADMIN = "admin" # 幹部

class UserModel(BaseModel):
    line_user_id: str = line_user_id_field
    student_id: Optional[str] = ""
    name: Optional[str] = ""
    role: UserRole = Field(default=UserRole.GENERAL)