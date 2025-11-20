from fastmcp import FastMCP, Context
from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.exceptions import ToolError
from fastmcp.server.dependencies import get_http_headers
from pymongo import MongoClient
from typing import Annotated, Literal
import os
import one_on_one
from mongo.schema import (
    OneOnOneFormModel, ScheduleModel, Schedule, WEEKDAYS, CLASS_PERIOD,
    UserModel, UserRole, Weekday, ClassPeriod, OneOnOneRole
)
import logging
from rich.logging import RichHandler

client = MongoClient(f"mongodb://{os.getenv('MONGO_INITDB_ROOT_USERNAME')}:{os.getenv('MONGO_INITDB_ROOT_PASSWORD')}@mongo:27017")
db = client["piano-club"]
db_users = db.users
db_one_on_one_enroll = db.one_on_one_enroll
db_one_on_one_schedule = db.one_on_one_schedule
logging.getLogger("pymongo").setLevel(logging.WARN)

mcp = FastMCP("piano-club")

logger = logging.getLogger(mcp.name)
logger.setLevel(logging.DEBUG)
logger.handlers = [RichHandler(show_time=False, show_level=False)]

# db_users.replace_one(
#     {"line_user_id": "U185a46e21c14044575e4a064a1719a43"},
#     UserModel(
#         line_user_id="U185a46e21c14044575e4a064a1719a43",
#         student_id="B11107051",
#         name="李品翰",
#         role=UserRole.ADMIN
#     ).model_dump(mode="json"),
#     upsert=True
# )

def get_line_user_id():
    authorization = get_http_headers().get("authorization")
    if authorization is None:
        raise ToolError("Unauthorized: Missing access token")

    scheme, line_user_id = authorization.split()
    if scheme.lower() != "bearer":
        raise ToolError("Unauthorized: Invalid authorization scheme")

    return line_user_id

def get_user():
    line_user_id = get_line_user_id()
    
    doc = db_users.find_one({"line_user_id": line_user_id})
    if doc is None:
        return None
    
    return UserModel.model_validate(doc)

class AuthMiddleware(Middleware):
    async def on_list_tools(self, context: MiddlewareContext, call_next):
        result = await call_next(context)
        
        user = get_user()
        if user is None:
            role = UserRole.GENERAL
        else:
            role = user.role
        
        filtered_tools = [
            tool for tool in result 
            if role in tool.tags
        ]
        return filtered_tools
    
    async def on_call_tool(self, context: MiddlewareContext, call_next):
        user = get_user()
        if user is None:
            role = UserRole.GENERAL
        else:
            role = user.role

        if context.fastmcp_context:
            tool = await context.fastmcp_context.fastmcp.get_tool(context.message.name)
            
            if role not in tool.tags:
                raise ToolError("Unauthorized: User does not have permission to call this tool")
        
        return await call_next(context)
mcp.add_middleware(AuthMiddleware())

def join_club(
    name: Annotated[str, "名字"],
    student_id: Annotated[str, "學號"],
):
    """加入鋼琴社，成為社員"""
    line_user_id = get_line_user_id()
    user = UserModel(
        line_user_id=line_user_id,
        student_id=student_id,
        name=name,
        role=UserRole.MEMBER
    )
    doc = db_users.find_one({"line_user_id": line_user_id})
    if doc is None:
        logger.info(f"使用者 {line_user_id} 新入社，名字 {name} 學號 {student_id}")
        result = db_users.insert_one(user.model_dump(mode="json"))
        logger.debug(result)
        return "入社成功"
    else:
        old_user = UserModel.model_validate(doc)
        if old_user.role in {UserRole.MEMBER, UserRole.ADMIN}:
            logger.info(f"使用者 {line_user_id} 重複入社，名字 {name} 學號 {student_id}")
            return "你已經是社員了，無需重複入社"
        else:
            logger.info(f"使用者 {line_user_id} 入社，名字 {name} 學號 {student_id}")
            result = db_users.replace_one({"line_user_id": line_user_id}, user.model_dump(mode="json"))
            logger.debug(result)
            return "入社成功"
mcp.tool(join_club, tags={UserRole.GENERAL})

def get_user_info():
    """取得使用者資訊"""
    user = get_user()
    if user is None:
        return "未找到使用者資訊"
    return user
mcp.tool(get_user_info, tags={UserRole.GENERAL, UserRole.MEMBER, UserRole.ADMIN})

def register_one_on_one_tutoring(
    role: Annotated[OneOnOneRole, "使用者想在一對一教學中擔任老師或學生?"],
    availble_time: Annotated[
        set[tuple[Weekday, ClassPeriod]],
        """使用者可以上課的所有時間，以台科大課程節次表示"""
    ]
) -> str:
    """報名一對一教學，在送出報名請求前，請先向使用者確認所有欄位皆正確再送出請求。"""
    logger.info(f"role: {role}")
    logger.info(f"availble_time: {availble_time}")
    line_user_id = get_line_user_id()
    db_one_on_one_enroll.replace_one(
        {"line_user_id": line_user_id},
        OneOnOneFormModel(
            line_user_id=line_user_id,
            role=role,
            availble_time=availble_time
        ).model_dump(mode="json"),
        upsert=True
    )
    return "報名成功"
mcp.tool(register_one_on_one_tutoring, tags={UserRole.MEMBER, UserRole.ADMIN})

def get_one_on_one_tutoring_registration():
    """取得使用者的一對一教學報名紀錄"""
    line_user_id = get_line_user_id()
    doc = db_one_on_one_enroll.find_one({"line_user_id": line_user_id}, {"_id": 0, "line_user_id": 0})
    if doc is None:
        return "未找到報名紀錄"
    else:
        return OneOnOneFormModel.model_validate(doc)
mcp.tool(get_one_on_one_tutoring_registration, tags={UserRole.MEMBER, UserRole.ADMIN})

def get_all_one_on_one_tutoring_registrations():
    """取得所有一對一教學報名紀錄"""
    
    return [
        OneOnOneFormModel.model_validate(form)
        for form in db_one_on_one_enroll.find({}, {"_id": 0, "line_user_id": 0})
    ]
mcp.tool(get_all_one_on_one_tutoring_registrations, tags={UserRole.ADMIN})

def update_one_on_one_tutoring_schedule():
    """更新並取得一對一教學課表"""
    forms = get_all_one_on_one_tutoring_registrations()
    users: dict[str, UserModel]= dict()
    with db_users.find(
        {"line_user_id": {"$in": [form.line_user_id for form in forms]}},
        {"_id": 0}
    ) as cursor:
        for user in cursor:
            user_model = UserModel.model_validate(user)
            users[user_model.line_user_id] = user_model
    result = one_on_one.schedule(
        students=[
            one_on_one.Student(
                available_time=form.availble_time,
                obj=form
            )
            for form in forms if form.role == "student"
        ],
        teachers=[
            one_on_one.Teacher(
                available_time=form.availble_time,
                max_students=1,
                obj=form
            )
            for form in forms if form.role == "teacher"
        ]
    )
    logger.info([f"{t.section}: {users[t.teacher.line_user_id].name} teach {users[t.student.line_user_id].name}" for t in result])
    
    schedule: Schedule = {
        weekday: {section: None for section in CLASS_PERIOD} for weekday in WEEKDAYS
    }
    for t in result:
        schedule[t.section[0]][t.section[1]] = {
            OneOnOneRole.TEACHER: users[t.teacher.line_user_id].name or "<無名稱>",
            OneOnOneRole.STUDENT: users[t.student.line_user_id].name or "<無名稱>"
        }
    schedule_model = ScheduleModel.model_validate(schedule)

    update_result = db_one_on_one_schedule.replace_one(
        {},
        schedule_model.model_dump(mode="json"),
        upsert=True
    )
    logger.info(update_result)
    return schedule_model
mcp.tool(update_one_on_one_tutoring_schedule, tags={UserRole.ADMIN})

def get_one_on_one_tutoring_schedule():
    """取得目前一對一教學課表"""
    doc = db_one_on_one_schedule.find_one({}, {"_id": 0})
    if doc is None:
        return "尚未有一對一教學課表，請等待幹部更新課表"
    return ScheduleModel.model_validate(doc)
mcp.tool(get_one_on_one_tutoring_schedule, tags={UserRole.GENERAL, UserRole.MEMBER, UserRole.ADMIN})