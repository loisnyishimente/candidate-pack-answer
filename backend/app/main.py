import json
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import date, datetime, time as dt_time, timezone

from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from .auth import current_user, require_roles
from .database import get_db
from .importer import import_csv
from .models import Assignment, DatasetRequest, Episode, Quality, RequestStatus, Role, StatusHistory, User
from .schemas import AssignmentIn, EpisodeOut, HistoryOut, LoginIn, LoginOut, RequestCreate, RequestOut, StatusChange, UserCreate, UserOut, UserUpdate
from .security import create_token, hash_password, verify_password

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(message)s")
logger = logging.getLogger("request-desk")


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="Dataset Request Desk", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","), allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def request_log(request: Request, call_next):
    started = time.perf_counter()
    user_id = None
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        from .security import decode_token
        user_id = decode_token(auth[7:])
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        logger.info(json.dumps({"method": request.method, "path": request.url.path, "status": status_code, "duration_ms": round((time.perf_counter() - started) * 1000, 2), "user_id": user_id}))


@app.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(select(1))
    return {"status": "ok"}


@app.post("/auth/login", response_model=LoginOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(func.lower(User.email) == payload.email.lower()))
    if not user or not user.active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    return LoginOut(access_token=create_token(user.id), user=user)


@app.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user


def request_out(item: DatasetRequest) -> RequestOut:
    result = RequestOut.model_validate(item)
    result.assigned_count = len(item.assignments)
    return result


@app.post("/requests", response_model=RequestOut, status_code=201)
def create_request(payload: RequestCreate, user: User = Depends(require_roles(Role.client)), db: Session = Depends(get_db)):
    item = DatasetRequest(client_id=user.id, **payload.model_dump())
    db.add(item)
    db.flush()
    db.add(StatusHistory(request_id=item.id, from_status=None, to_status=RequestStatus.submitted, changed_by=user.id))
    db.commit(); db.refresh(item)
    return request_out(item)


@app.get("/requests", response_model=list[RequestOut])
def list_requests(user: User = Depends(current_user), db: Session = Depends(get_db)):
    query = select(DatasetRequest).options(selectinload(DatasetRequest.assignments)).order_by(DatasetRequest.created_at.desc())
    if user.role == Role.client:
        query = query.where(DatasetRequest.client_id == user.id)
    return [request_out(item) for item in db.scalars(query).all()]


def owned_request(request_id: int, user: User, db: Session) -> DatasetRequest:
    item = db.scalar(select(DatasetRequest).options(selectinload(DatasetRequest.assignments)).where(DatasetRequest.id == request_id))
    if not item or (user.role == Role.client and item.client_id != user.id):
        raise HTTPException(404, "Request not found")
    return item


@app.get("/requests/{request_id}", response_model=RequestOut)
def get_request(request_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return request_out(owned_request(request_id, user, db))


TRANSITIONS = {
    Role.client: {(RequestStatus.delivered, RequestStatus.accepted), (RequestStatus.delivered, RequestStatus.rejected)},
    Role.operator: {(RequestStatus.submitted, RequestStatus.in_progress), (RequestStatus.in_progress, RequestStatus.delivered), (RequestStatus.rejected, RequestStatus.in_progress)},
    Role.admin: {(RequestStatus.submitted, RequestStatus.in_progress), (RequestStatus.in_progress, RequestStatus.delivered), (RequestStatus.rejected, RequestStatus.in_progress)},
}


@app.post("/requests/{request_id}/status", response_model=RequestOut)
def change_status(request_id: int, payload: StatusChange, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = owned_request(request_id, user, db)
    if (item.status, payload.status) not in TRANSITIONS[user.role]:
        raise HTTPException(409, f"Invalid transition: {item.status.value} -> {payload.status.value}")
    if payload.status == RequestStatus.delivered and len(item.assignments) < item.episodes_requested:
        raise HTTPException(409, "Not enough episodes assigned")
    old = item.status
    item.status = payload.status
    db.add(StatusHistory(request_id=item.id, from_status=old, to_status=payload.status, changed_by=user.id))
    db.commit(); db.refresh(item)
    return request_out(item)


@app.get("/requests/{request_id}/history", response_model=list[HistoryOut])
def request_history(request_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    owned_request(request_id, user, db)
    return db.scalars(select(StatusHistory).where(StatusHistory.request_id == request_id).order_by(StatusHistory.changed_at)).all()


@app.get("/episodes", response_model=list[EpisodeOut])
def episodes(task_name: str | None = None, quality: Quality | None = None, available: bool = True, limit: int = Query(100, ge=1, le=500), user: User = Depends(require_roles(Role.operator, Role.admin)), db: Session = Depends(get_db)):
    query = select(Episode).order_by(Episode.recorded_at.desc()).limit(limit)
    if task_name: query = query.where(func.lower(Episode.task_name).contains(task_name.lower()))
    if quality: query = query.where(Episode.quality == quality)
    if available: query = query.outerjoin(Assignment).where(Assignment.id.is_(None))
    return db.scalars(query).all()


@app.post("/requests/{request_id}/assignments", response_model=RequestOut)
def assign(request_id: int, payload: AssignmentIn, user: User = Depends(require_roles(Role.operator, Role.admin)), db: Session = Depends(get_db)):
    item = owned_request(request_id, user, db)
    if item.status not in (RequestStatus.in_progress, RequestStatus.rejected):
        raise HTTPException(409, "Episodes can only be assigned while work is in progress")
    if len(set(payload.episode_ids)) != len(payload.episode_ids):
        raise HTTPException(422, "episode_ids must be unique")
    found = db.scalars(select(Episode).where(Episode.id.in_(payload.episode_ids))).all()
    if len(found) != len(payload.episode_ids): raise HTTPException(404, "One or more episodes were not found")
    if any(e.quality == Quality.bad for e in found): raise HTTPException(409, "Bad-quality episodes cannot be assigned")
    for episode in found: db.add(Assignment(request_id=item.id, episode_id=episode.id, assigned_by=user.id))
    try:
        db.commit()
    except IntegrityError:
        db.rollback(); raise HTTPException(409, "An episode is already assigned")
    db.refresh(item)
    return request_out(item)


@app.post("/episodes/import")
def upload_episodes(file: UploadFile = File(...), user: User = Depends(require_roles(Role.operator, Role.admin)), db: Session = Depends(get_db)):
    if not file.filename or not file.filename.lower().endswith(".csv"): raise HTTPException(422, "A CSV file is required")
    try: return import_csv(db, file.file.read())
    except ValueError as exc: raise HTTPException(422, str(exc))


@app.get("/analytics")
def analytics(start: date, end: date, user: User = Depends(require_roles(Role.operator, Role.admin)), db: Session = Depends(get_db)):
    if end < start: raise HTTPException(422, "end must be on or after start")
    start_dt = datetime.combine(start, dt_time.min, tzinfo=timezone.utc); end_dt = datetime.combine(end, dt_time.max, tzinfo=timezone.utc)
    day_expr = func.date(Episode.recorded_at)
    recorded = db.execute(select(day_expr.label("day"), Episode.robot_id, func.count().label("count")).where(Episode.recorded_at.between(start_dt, end_dt)).group_by(day_expr, Episode.robot_id).order_by(day_expr, Episode.robot_id)).mappings().all()
    statuses = db.execute(select(DatasetRequest.status, func.count().label("count")).where(DatasetRequest.created_at.between(start_dt, end_dt)).group_by(DatasetRequest.status)).all()
    submitted = select(StatusHistory.request_id, func.min(StatusHistory.changed_at).label("submitted_at")).where(StatusHistory.to_status == RequestStatus.submitted).group_by(StatusHistory.request_id).subquery()
    delivered = select(StatusHistory.request_id, func.min(StatusHistory.changed_at).label("delivered_at")).where(StatusHistory.to_status == RequestStatus.delivered).group_by(StatusHistory.request_id).subquery()
    joined = select(submitted.c.submitted_at, delivered.c.delivered_at).join(delivered, submitted.c.request_id == delivered.c.request_id).join(DatasetRequest, DatasetRequest.id == submitted.c.request_id).where(DatasetRequest.created_at.between(start_dt, end_dt)).subquery()
    if db.bind.dialect.name == "postgresql":
        duration = func.extract("epoch", joined.c.delivered_at - joined.c.submitted_at)
        median_query = select(func.percentile_cont(0.5).within_group(duration))
    else:
        # SQLite test/dev fallback: AVG of the middle one/two ranked values, still entirely in SQL.
        duration = (func.julianday(joined.c.delivered_at) - func.julianday(joined.c.submitted_at)) * 86400.0
        ranked = select(duration.label("seconds"), func.row_number().over(order_by=duration).label("rn"), func.count().over().label("n")).subquery()
        median_query = select(func.avg(ranked.c.seconds)).where(ranked.c.rn.in_(((ranked.c.n + 1) / 2, (ranked.c.n + 2) / 2)))
    median = db.scalar(median_query)
    top = db.execute(select(Episode.task_name, func.count().label("count")).where(Episode.quality == Quality.good, Episode.recorded_at.between(start_dt, end_dt)).group_by(Episode.task_name).order_by(func.count().desc()).limit(5)).mappings().all()
    return {"episodes_per_day_robot": [dict(x) for x in recorded], "requests_by_status": {s.value: c for s,c in statuses}, "median_submission_to_delivery_seconds": median, "top_good_tasks": [dict(x) for x in top]}


@app.get("/users", response_model=list[UserOut])
def users(user: User = Depends(require_roles(Role.admin)), db: Session = Depends(get_db)):
    return db.scalars(select(User).order_by(User.name)).all()


@app.post("/users", response_model=UserOut, status_code=201)
def create_user(payload: UserCreate, user: User = Depends(require_roles(Role.admin)), db: Session = Depends(get_db)):
    item = User(**payload.model_dump(exclude={"password"}), password_hash=hash_password(payload.password), email=payload.email.lower())
    db.add(item)
    try: db.commit()
    except IntegrityError: db.rollback(); raise HTTPException(409, "Email already exists")
    db.refresh(item); return item


@app.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, payload: UserUpdate, user: User = Depends(require_roles(Role.admin)), db: Session = Depends(get_db)):
    item = db.get(User, user_id)
    if not item: raise HTTPException(404, "User not found")
    if item.id == user.id and payload.active is False: raise HTTPException(409, "You cannot deactivate yourself")
    for key, value in payload.model_dump(exclude_none=True).items(): setattr(item, key, value)
    db.commit(); db.refresh(item); return item
