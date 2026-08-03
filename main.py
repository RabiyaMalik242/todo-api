"""
Task API - a small CRUD API for managing a to-do list.
FlyRank Internship · Backend Track · W2 · A1

In-memory storage only (no database) - data resets on restart, by design.
Run with: uvicorn main:app --reload --port 8000
Docs at:  http://localhost:8000/docs
"""

from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, field_validator
from typing import Optional

app = FastAPI(
    title="Task API",
    version="1.0",
    description="A small in-memory CRUD API for managing tasks.",
)

# ---------------------------------------------------------------------------
# In-memory "database" - just a Python list. Gone on restart (that's Week 3).
# ---------------------------------------------------------------------------

DEFAULT_TASKS = [
    {"id": 1, "title": "Buy milk", "done": False},
    {"id": 2, "title": "Write README", "done": False},
    {"id": 3, "title": "Ship the API", "done": True},
]

tasks = [dict(t) for t in DEFAULT_TASKS]
next_id = len(tasks) + 1


# ---------------------------------------------------------------------------
# Request/response models
# ---------------------------------------------------------------------------

class TaskCreate(BaseModel):
    title: str

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("title must not be empty")
        return v


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    done: Optional[bool] = None

    @field_validator("title")
    @classmethod
    def title_not_empty_if_given(cls, v):
        if v is not None and not v.strip():
            raise ValueError("title must not be empty")
        return v


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def find_task(task_id: int):
    return next((t for t in tasks if t["id"] == task_id), None)


def error(msg: str):
    """Uniform JSON error shape: { "error": "..." }"""
    return {"error": msg}


# ---------------------------------------------------------------------------
# Stage 1 - root and health
# ---------------------------------------------------------------------------

@app.get("/", tags=["meta"], summary="API description")
def root():
    return {"name": "Task API", "version": "1.0", "endpoints": ["/tasks"]}


@app.get("/health", tags=["meta"], summary="Liveness check")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Stage 2 - read
# ---------------------------------------------------------------------------

@app.get("/tasks", tags=["tasks"], summary="List tasks (filter/search/paginate)")
def list_tasks(
    done: Optional[bool] = None,
    search: Optional[str] = None,
    limit: Optional[int] = None,
    offset: int = 0,
):
    result = tasks

    if done is not None:
        result = [t for t in result if t["done"] == done]

    if search:
        needle = search.lower()
        result = [t for t in result if needle in t["title"].lower()]

    # Pagination (stretch goal) - real APIs never return "everything"; it
    # protects both server and client from unbounded response sizes.
    result = result[offset:]
    if limit is not None:
        result = result[:limit]

    return result


@app.get("/tasks/{task_id}", tags=["tasks"], summary="Get one task")
def get_task(task_id: int):
    task = find_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return task


@app.get("/stats", tags=["tasks"], summary="Task counts")
def stats():
    total = len(tasks)
    done_count = sum(1 for t in tasks if t["done"])
    return {"total": total, "done": done_count, "open": total - done_count}


# ---------------------------------------------------------------------------
# Stage 3 - create
# ---------------------------------------------------------------------------

@app.post("/tasks", status_code=201, tags=["tasks"], summary="Create a task")
def create_task(payload: TaskCreate):
    global next_id
    task = {"id": next_id, "title": payload.title, "done": False}
    tasks.append(task)
    next_id += 1
    return task


# ---------------------------------------------------------------------------
# Stage 4 - update and delete
# ---------------------------------------------------------------------------

@app.put("/tasks/{task_id}", tags=["tasks"], summary="Update a task")
def update_task(task_id: int, payload: TaskUpdate):
    task = find_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    if payload.title is None and payload.done is None:
        raise HTTPException(status_code=400, detail="Provide title and/or done to update")

    if payload.title is not None:
        task["title"] = payload.title
    if payload.done is not None:
        task["done"] = payload.done

    return task


@app.delete("/tasks/{task_id}", status_code=204, tags=["tasks"], summary="Delete a task")
def delete_task(task_id: int):
    task = find_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    tasks.remove(task)
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Extras - seed and reset (handy for demos, and for the mortality experiment)
# ---------------------------------------------------------------------------

@app.post("/reset", tags=["meta"], summary="Restore the 3 example tasks")
def reset():
    global tasks, next_id
    tasks = [dict(t) for t in DEFAULT_TASKS]
    next_id = len(tasks) + 1
    return {"status": "reset", "tasks": tasks}


# ---------------------------------------------------------------------------
# Turn Pydantic validation errors (422) into the assignment's 400 + {"error": ...}
# ---------------------------------------------------------------------------

from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    first = exc.errors()[0]
    field = ".".join(str(p) for p in first["loc"] if p != "body")
    return JSONResponse(status_code=400, content=error(f"Invalid input: {field} — {first['msg']}"))


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content=error(exc.detail))
