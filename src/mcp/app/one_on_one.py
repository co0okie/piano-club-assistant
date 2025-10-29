from ortools.graph.python.max_flow import SimpleMaxFlow
from typing import TypeVar, Generic, TypedDict
from pydantic import BaseModel
import random

StudentType = TypeVar("StudentType")
Section = TypeVar("Section")
TeacherType = TypeVar("TeacherType")

class Teacher(BaseModel, Generic[StudentType, Section]):
    obj: StudentType
    max_students: int = 1
    available_time: set[Section] = set()

class Student(BaseModel, Generic[StudentType, Section]):
    obj: StudentType
    available_time: set[Section] = set()


class SectionStudentTeacher(BaseModel, Generic[Section, StudentType, TeacherType]):
    section: Section
    student: StudentType
    teacher: TeacherType

def schedule(
    students: list[Student[StudentType, Section]],
    teachers: list[Teacher[TeacherType, Section]],
) -> list[SectionStudentTeacher[Section, StudentType, TeacherType]]:
    if not students or not teachers:
        return []
    # all possible time slots
    sections = list(set[Section].union(
        *[s.available_time for s in students],
        *[t.available_time for t in teachers]
    ))
    section2id = {v: i for i, v in enumerate(sections)} # without offset

    max_flow = SimpleMaxFlow()

    # assign every nodes to a unique id
    student_source = 0
    students_offset = student_source + 1
    students_p_offset = students_offset + len(students)
    sections_offset = students_p_offset + len(students)
    sections_p_offset = sections_offset + len(sections)
    teachers_offset = sections_p_offset + len(sections)
    teachers_p_offset = teachers_offset + len(teachers)
    teacher_sink = teachers_p_offset + len(teachers)

    # build the graph
    student_section_edges: list[int] = []
    section_teacher_edges: list[int] = []
    for i, student in enumerate(students):
        student_id = students_offset + i
        student_p_id = students_p_offset + i
        max_flow.add_arc_with_capacity(student_source, student_id, 1)
        max_flow.add_arc_with_capacity(student_id, student_p_id, 1)
        for section in student.available_time:
            section_id = sections_offset + section2id[section]
            edge_id = max_flow.add_arc_with_capacity(student_p_id, section_id, 1)
            student_section_edges.append(edge_id)

    for section, i in section2id.items():
        section_id = sections_offset + i
        section_p_id = sections_p_offset + i
        max_flow.add_arc_with_capacity(section_id, section_p_id, 1)

    for i, teacher in enumerate(teachers):
        teacher_id = teachers_offset + i
        teacher_p_id = teachers_p_offset + i
        for section in teacher.available_time:
            section_p_id = sections_p_offset + section2id[section]
            edge_id = max_flow.add_arc_with_capacity(section_p_id, teacher_id, 1)
            section_teacher_edges.append(edge_id)
        max_flow.add_arc_with_capacity(teacher_id, teacher_p_id, teacher.max_students)
        max_flow.add_arc_with_capacity(teacher_p_id, teacher_sink, teacher.max_students)
    
    max_flow.solve(student_source, teacher_sink)
    
    student_section_edges_solution = [edge for edge in student_section_edges if max_flow.flow(edge) > 0]
    section_teacher_edges_solution = [edge for edge in section_teacher_edges if max_flow.flow(edge) > 0]
    
    # combine (student -> section) and (section -> teacher) into (section, student, teacher)
    section2student = {
        sections[section_id]: students[student_id].obj
        for student_id, section_id in [
            (max_flow.tail(edge) - students_p_offset, max_flow.head(edge) - sections_offset)
            for edge in student_section_edges_solution
        ]
    }
    section_student_teacher = [
        SectionStudentTeacher(
            section=sections[section_id],
            student=section2student[sections[section_id]],
            teacher=teachers[teacher_id].obj
        )
        for section_id, teacher_id in [
            (max_flow.tail(edge) - sections_p_offset, max_flow.head(edge) - teachers_offset)
            for edge in section_teacher_edges_solution
        ]
    ]
    return section_student_teacher

if __name__ == "__main__":
    WEEKDAYS = ("M", "T", "W", "R", "F", "S", "U")
    SECTIONS = ("1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "A", "B", "C", "D")
    def make_random_example(
        n_students=3, n_teachers=2,
        max_section=6
    ):
        rng = random.Random()
        students = [
            Student(
                # available_time={rng.randint(1, max_section) for _ in range(rng.randint(1, max_section))},
                available_time={f"""{WEEKDAYS[rng.randint(0, 6)]}{SECTIONS[rng.randint(0, 13)]}""" 
                                for _ in range(rng.randint(1, max_section))},
                obj=f"student{i+1}"
            )
            for i in range(n_students)
        ]
        teachers = [
            Teacher(
                # available_time={rng.randint(1, max_section) for _ in range(rng.randint(1, max_section))},
                available_time={f"""{WEEKDAYS[rng.randint(0, 6)]}{SECTIONS[rng.randint(0, 13)]}""" 
                                for _ in range(rng.randint(1, max_section))},
                max_students=1,
                obj=f"teacher{j+1}"
            )
            for j in range(n_teachers)
        ]
        return students, teachers
    
    
    students, teachers = make_random_example(
        n_students=5, 
        n_teachers=5, 
        max_section=30
    )

    print("student, available_time:")
    for s in students:
        print(f"  {s.obj}, {s.available_time}")

    print("teacher, available_time, max_students:")
    for t in teachers:
        print(f"  {t.obj}, {t.available_time}, {t.max_students}")

    solution = schedule(students, teachers)

    print("solution:")
    for t in solution:
        print(f"  {t.section}: {t.teacher}, {t.student}")