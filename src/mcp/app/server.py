from fastmcp import FastMCP, Context
from rich import print
import requests
from typing import Annotated, Literal
from dataclasses import dataclass
import json

mcp = FastMCP("piano-club-assistant")

@mcp.tool
def one_on_one_teaching_enrollment(
    conversation_id: Annotated[str, "Conversation ID"],
    name: Annotated[str, "ask user for his/her name"],
    role: Annotated[
        Literal["teacher", "student"],
        "ask user if he/she wants to be a teacher or a student"
    ],
    availble_time: Annotated[
        set[tuple[
            Literal["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
            Literal["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "A", "B", "C", "D"]
        ]],
        """ask user for all of his/her available session time slots
e.g., ('Mon', '1') means Monday session 1, ('Fri', 'A') means Friday session A, etc.
The day of the week: Mon, Tue, Wed, Thu, Fri, Sat, Sun
Session time slot:
    1: 08:10-09:00
    2: 09:10-10:00
    3: 10:20-11:10
    4: 11:20-12:10
    5: 12:20-13:10
    6: 13:20-14:10
    7: 14:20-15:10
    8: 15:30-16:20
    9: 16:30-17:20
    10: 17:20-18:10
    A: 18:25-19:15
    B: 19:20-20:10
    C: 20:15-21:05
    D: 21:10-22:00"""
    ]
) -> bool:
    """Facilitate one-on-one teaching registration by asking the user for the required information. Ask only one question at a time instead of presenting everything at once. Do not fabricate any answers—make sure all information comes directly from the user."""
    print(f"conversation_id: {conversation_id}")
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

    requests.post("http://api:8000/one-on-one", json={
        "conversation_id": conversation_id,
        "name": name,
        "role": role,
        "availble_time": [[weekday_abbreviate(day), time] for day, time in availble_time]
    })
    return True


@mcp.tool
def fetch_one_on_one_teaching_enrollment_record(
    conversation_id: Annotated[str, "Conversation ID"]
):
    """Fetch one-on-one teaching enrollment record."""
    response = requests.get(f"http://api:8000/one-on-one/{conversation_id}")
    return response.json()
    

# @dataclass
# class SessionTable:
#     Mon1: bool
#     Mon2: bool
#     Mon3: bool
#     Mon4: bool
#     Mon5: bool
#     Mon6: bool
#     Mon7: bool
#     Mon8: bool
#     Mon9: bool
#     Mon10: bool
#     MonA: bool
#     MonB: bool
#     MonC: bool
#     MonD: bool
#     Tue1: bool
#     Tue2: bool
#     Tue3: bool
#     Tue4: bool
#     Tue5: bool
#     Tue6: bool
#     Tue7: bool
#     Tue8: bool
#     Tue9: bool
#     Tue10: bool
#     TueA: bool
#     TueB: bool
#     TueC: bool
#     TueD: bool
#     Wed1: bool
#     Wed2: bool
#     Wed3: bool
#     Wed4: bool
#     Wed5: bool
#     Wed6: bool
#     Wed7: bool
#     Wed8: bool
#     Wed9: bool
#     Wed10: bool
#     WedA: bool
#     WedB: bool
#     WedC: bool
#     WedD: bool
#     Thu1: bool
#     Thu2: bool
#     Thu3: bool
#     Thu4: bool
#     Thu5: bool
#     Thu6: bool
#     Thu7: bool
#     Thu8: bool
#     Thu9: bool
#     Thu10: bool
#     ThuA: bool
#     ThuB: bool
#     ThuC: bool
#     ThuD: bool
#     Fri1: bool
#     Fri2: bool
#     Fri3: bool
#     Fri4: bool
#     Fri5: bool
#     Fri6: bool
#     Fri7: bool
#     Fri8: bool
#     Fri9: bool
#     Fri10: bool
#     FriA: bool
#     FriB: bool
#     FriC: bool
#     FriD: bool
#     Sat1: bool
#     Sat2: bool
#     Sat3: bool
#     Sat4: bool
#     Sat5: bool
#     Sat6: bool
#     Sat7: bool
#     Sat8: bool
#     Sat9: bool
#     Sat10: bool
#     SatA: bool
#     SatB: bool
#     SatC: bool
#     SatD: bool
#     Sun1: bool
#     Sun2: bool
#     Sun3: bool
#     Sun4: bool
#     Sun5: bool
#     Sun6: bool
#     Sun7: bool
#     Sun8: bool
#     Sun9: bool
#     Sun10: bool
#     SunA: bool
#     SunB: bool
#     SunC: bool
#     SunD: bool

# @mcp.tool
# async def one_on_one_teaching_enrollment(
#     conversation_id: Annotated[str, "Conversation ID"],
#     ctx: Context
# ) -> str:
#     """Facilitate one-on-one teaching registration by asking the user for the required information. Ask only one question at a time instead of presenting everything at once. Do not fabricate any answers—make sure all information comes directly from the user."""

#     name_result = await ctx.elicit("What is the user's name?", str)
#     if name_result.action != "accept":
#         return "One-on-one teaching enrollment cancelled"
    
#     role_result = await ctx.elicit(
#         "Does user want to be a teacher or a student?", 
#         Literal["teacher", "student"]
#     )
#     if role_result.action != "accept":
#         return "One-on-one teaching enrollment cancelled"
    
#     availble_time_result = await ctx.elicit(
#         """What are all of the user's available session time slots?
# e.g., Mon1 means Monday session 1, FriA means Friday session A, etc.
# The day of the week: Mon, Tue, Wed, Thu, Fri, Sat, Sun
# Session time slot:
#     1: 08:10-09:00
#     2: 09:10-10:00
#     3: 10:20-11:10
#     4: 11:20-12:10
#     5: 12:20-13:10
#     6: 13:20-14:10
#     7: 14:20-15:10
#     8: 15:30-16:20
#     9: 16:30-17:20
#     10: 17:20-18:10
#     A: 18:25-19:15
#     B: 19:20-20:10
#     C: 20:15-21:05
#     D: 21:10-22:00""",
#         SessionTable
#     )
#     if availble_time_result.action != "accept":
#         return "One-on-one teaching enrollment cancelled"
    
#     print(f"name: {name_result.data}")
#     print(f"role: {role_result.data}")
#     print(f"availble_time: {availble_time_result.data}")
#     return "One-on-one teaching enrollment completed"