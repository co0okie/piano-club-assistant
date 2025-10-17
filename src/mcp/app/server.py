from fastmcp import FastMCP, Context
from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.exceptions import ToolError
from fastmcp.server.dependencies import get_http_headers
from rich import print
from pymongo import MongoClient
from typing import Annotated, Literal
import os
import one_on_one_teaching
from mongo.schema import (
    OneOnOneFormModel, ScheduleModel, Schedule, WEEKDAYS, SECTIONS,
    UserModel, UserRole
)
import logging
from rich.logging import RichHandler

client = MongoClient(f"mongodb://{os.getenv('MONGO_INITDB_ROOT_USERNAME')}:{os.getenv('MONGO_INITDB_ROOT_PASSWORD')}@mongo:27017")
db = client["piano-club"]
one_on_one_enroll_collection = db["one-on-one-teaching-enrollments"]
one_on_one_schedule_collection = db["one-on-one-teaching-schedule"]
logging.getLogger("pymongo").setLevel(logging.WARN)

mcp = FastMCP("piano-club")

logger = logging.getLogger(mcp.name)
logger.setLevel(logging.DEBUG)
logger.handlers = [RichHandler(show_time=False, show_level=False)]

# db.users.replace_one(
#     {"line_user_id": "U185a46e21c14044575e4a064a1719a43"},
#     UserModel(
#         line_user_id="U185a46e21c14044575e4a064a1719a43",
#         student_id="B11107051",
#         name="李品翰",
#         role=UserRole.ADMIN
#     ).model_dump(mode="json"),
#     upsert=True
# )

def get_user():
    authorization = get_http_headers().get("authorization")

    if authorization is None:
        raise ToolError("Unauthorized: Missing access token")

    scheme, line_user_id = authorization.split()

    if scheme.lower() != "bearer":
        raise ToolError("Unauthorized: Invalid authorization scheme")
    
    doc = db.users.find_one({"line_user_id": line_user_id})

    if doc is None:
        raise ToolError("Unauthorized: User not found")
    
    return UserModel.model_validate(doc)

class AuthMiddleware(Middleware):
    async def on_list_tools(self, context: MiddlewareContext, call_next):
        result = await call_next(context)
        
        user = get_user()
        
        filtered_tools = [
            tool for tool in result 
            if user.role in tool.tags
        ]
        
        return filtered_tools
    
    async def on_call_tool(self, context: MiddlewareContext, call_next):
        user = get_user()

        if context.fastmcp_context:
            tool = await context.fastmcp_context.fastmcp.get_tool(context.message.name)
            
            if user.role not in tool.tags:
                raise ToolError("Unauthorized: User does not have permission to call this tool")
        
        return await call_next(context)
mcp.add_middleware(AuthMiddleware())

def join_piano_club():
    pass

def register_one_on_one_tutoring(
    role: Annotated[
        Literal["teacher", "student"],
        "使用者想在一對一教學中擔任老師或學生?"
    ],
    student_id: Annotated[str, "學號"],
    name: Annotated[str, "名字"],
    availble_time: Annotated[
        set[tuple[
            Literal["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
            Literal["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "A", "B", "C", "D"]
        ]],
        """使用者可以上課的所有時間，以台科大上課節次表示
例如，("Mon", "1") 代表星期一第一節課, ("Fri", "A") 代表星期五第A節課，依此類推"""
    ]
) -> str:
    """報名一對一教學，在送出報名請求前，請先向使用者確認所有欄位皆正確再送出請求。"""
    print(f"student_id: {student_id}")
    print(f"name: {name}")
    print(f"role: {role}")
    print(f"availble_time: {availble_time}")

    def weekday_abbreviate(day: Literal["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]):
        match day:
            case "Mon": return "M"
            case "Tue": return "T"
            case "Wed": return "W"
            case "Thu": return "R"
            case "Fri": return "F"
            case "Sat": return "S"
            case "Sun": return "U"
    
    one_on_one_enroll_collection.replace_one(
        {"student_id": student_id},
        {
            "student_id": student_id,
            "name": name,
            "role": role,
            "availble_time": [[weekday_abbreviate(day), time] for day, time in availble_time]
        },
        upsert=True
    )
    return "報名成功"
mcp.tool(register_one_on_one_tutoring, tags={UserRole.MEMBER, UserRole.ADMIN})

def get_one_on_one_tutoring_registration(
    student_id: Annotated[str, "使用者的學號"]
):
    """取得某個學號的一對一教學報名紀錄"""

    doc = one_on_one_enroll_collection.find_one({"student_id": student_id}, {"_id": 0})
    return doc
mcp.tool(get_one_on_one_tutoring_registration, tags={UserRole.MEMBER, UserRole.ADMIN})

def get_all_one_on_one_tutoring_registrations():
    """取得所有一對一教學報名紀錄"""
    
    return [
        OneOnOneFormModel.model_validate(form)
        for form in one_on_one_enroll_collection.find({}, {"_id": 0})
    ]
mcp.tool(get_all_one_on_one_tutoring_registrations, tags={UserRole.ADMIN})

def update_one_on_one_tutoring_schedule():
    """取得一對一教學課表
M: Monday
T: Tuesday
W: Wednesday
R: Thursday
F: Friday
S: Saturday
U: Sunday

Session time slot (第幾節): 1~10, A~D"""
    
    forms = get_all_one_on_one_tutoring_registrations()
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
mcp.tool(update_one_on_one_tutoring_schedule, tags={UserRole.ADMIN})

def get_one_on_one_tutoring_schedule():
    """取得目前一對一教學課表"""
    doc = one_on_one_schedule_collection.find_one({}, {"_id": 0})
    if doc is None:
        return None
    return ScheduleModel.model_validate(doc)
mcp.tool(get_one_on_one_tutoring_schedule, tags={UserRole.GENERAL, UserRole.MEMBER, UserRole.ADMIN})