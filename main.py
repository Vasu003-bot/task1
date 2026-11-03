from fastapi import FastAPI, HTTPException, Query
# FastAPI builds the API; HTTPException sends error codes like 404
from pydantic import BaseModel, ConfigDict, Field
# Pydantic checks that incoming data is valid
import sqlite3
# sqlite3 is built into Python and connects to the SQLite database

app = FastAPI(title="Task Manager")

DB_NAME = "main.db"


def get_db():
    conn = sqlite3.connect(DB_NAME)  # connect Python to the database file
    conn.row_factory = sqlite3.Row   # lets us read columns by name
    return conn


def init_db():
    conn = get_db()
    conn.execute(
        """CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            completed INTEGER NOT NULL DEFAULT 0
        )"""
    )
    conn.commit()
    conn.close()


init_db()
print("table ready")


class TaskCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    title: str = Field(..., min_length=1, max_length=100)
    description: str | None = None  # optional


class TaskUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    title: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    completed: bool | None = None


def row_to_dict(row):
    task = dict(row)
    task["completed"] = bool(task["completed"])  # 0/1 -> false/true
    return task


def find_task(conn, task_id: int):
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Task not found")
    return row


@app.get("/")
def home():
    return {"message": "Welcome to Task Manager API"}


@app.post("/tasks", status_code=201)
def create_task(task: TaskCreate):
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO tasks (title, description) VALUES (?, ?)",
        (task.title, task.description),
    )
    conn.commit()
    new_task = find_task(conn, cursor.lastrowid)
    conn.close()
    return row_to_dict(new_task)


@app.get("/tasks")
def get_tasks(status: str = Query("all", pattern="^(all|completed|pending)$")):
    conn = get_db()
    if status == "completed":
        rows = conn.execute("SELECT * FROM tasks WHERE completed = 1").fetchall()
    elif status == "pending":
        rows = conn.execute("SELECT * FROM tasks WHERE completed = 0").fetchall()
    else:
        rows = conn.execute("SELECT * FROM tasks").fetchall()
    conn.close()
    return [row_to_dict(r) for r in rows]


@app.get("/tasks/{task_id}")
def get_task(task_id: int):
    conn = get_db()
    task = find_task(conn, task_id)
    conn.close()
    return row_to_dict(task)


@app.put("/tasks/{task_id}")
def update_task(task_id: int, task: TaskUpdate):
    conn = get_db()
    find_task(conn, task_id)  # 404 if it does not exist

    updates = task.model_dump(exclude_unset=True)
    for field, value in updates.items():
        if value is None and field != "description":
            continue  # title and completed cannot be null
        if field == "completed":
            value = int(value)
        # field names come from our own model, so this f-string is safe
        conn.execute(f"UPDATE tasks SET {field} = ? WHERE id = ?", (value, task_id))
    conn.commit()

    updated = find_task(conn, task_id)
    conn.close()
    return row_to_dict(updated)


@app.patch("/tasks/{task_id}/toggle")
def toggle_task(task_id: int):
    conn = get_db()
    task = find_task(conn, task_id)
    conn.execute(
        "UPDATE tasks SET completed = ? WHERE id = ?",
        (0 if task["completed"] else 1, task_id),
    )
    conn.commit()
    updated = find_task(conn, task_id)
    conn.close()
    return row_to_dict(updated)


@app.delete("/tasks/{task_id}")
def delete_task(task_id: int):
    conn = get_db()
    find_task(conn, task_id)
    conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
    return {"message": "Task deleted successfully"}