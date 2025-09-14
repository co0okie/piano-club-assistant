from fastapi import FastAPI, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
import database, models
from typing import Optional
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    models.Base.metadata.create_all(bind=database.engine)
    yield

app = FastAPI(lifespan=lifespan)

# 依賴：提供 DB session
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

@app.post("/enroll")
def enroll(name: str, role: str, message: str = "", db: Session = Depends(get_db)):
    enrollment = models.Enrollment(name=name, role=role, message=message)
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)
    return {"id": enrollment.id, "name": enrollment.name, "role": enrollment.role}


@app.get("/enrollments")
def list_enrollments(
    role: Optional[str] = Query(None, description='篩選角色："student" 或 "teacher"'),
    q: Optional[str] = Query(None, description="關鍵字搜尋（比對 name / message）"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(models.Enrollment)

    if role:
        query = query.filter(models.Enrollment.role == role)

    if q:
        like = f"%{q}%"
        query = query.filter(or_(models.Enrollment.name.ilike(like),
                                 models.Enrollment.message.ilike(like)))

    total = query.count()
    rows = (query
            .order_by(models.Enrollment.id.desc())
            .offset(offset)
            .limit(limit)
            .all())

    items = [
        {
            "id": r.id,
            "name": r.name,
            "role": r.role,
            "message": r.message,
        }
        for r in rows
    ]

    return {"total": total, "limit": limit, "offset": offset, "items": items}