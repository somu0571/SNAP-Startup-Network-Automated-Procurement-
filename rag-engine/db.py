"""
SQLite database layer.
Stores problems, solutions, scores, and all intermediate JSON for debugging.
"""
import sqlite3
import json
import os
from config import SQLITE_DB_PATH

def get_connection():
    """Return a sqlite3 connection with row_factory set."""
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    """Create tables if they don't exist."""
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS problems (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            raw_text TEXT NOT NULL,
            requirements_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS solutions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            problem_id INTEGER NOT NULL,
            startup_name TEXT DEFAULT 'Unknown',
            filename TEXT,
            raw_text TEXT,
            solution_json TEXT,
            eligible INTEGER DEFAULT 1,
            eligibility_reason TEXT DEFAULT '',
            consistency_flags TEXT DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (problem_id) REFERENCES problems(id)
        );

        CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            solution_id INTEGER NOT NULL,
            problem_id INTEGER NOT NULL,
            relevance REAL,
            feasibility REAL,
            innovation REAL,
            team_credibility REAL,
            pilot_readiness REAL,
            justification_json TEXT,
            final_score REAL,
            scores_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (solution_id) REFERENCES solutions(id),
            FOREIGN KEY (problem_id) REFERENCES problems(id)
        );
    """)
    try:
        conn.execute("ALTER TABLE scores ADD COLUMN scores_json TEXT")
    except Exception:
        pass
    conn.commit()
    conn.close()


# ── Problem CRUD ─────────────────────────────────────────

def insert_problem(raw_text: str, requirements_json: dict) -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO problems (raw_text, requirements_json) VALUES (?, ?)",
        (raw_text, json.dumps(requirements_json))
    )
    pid = cur.lastrowid
    conn.commit()
    conn.close()
    return pid

def get_problem(problem_id) -> dict | None:
    conn = get_connection()
    try:
        pid = int(problem_id) if str(problem_id).isdigit() else problem_id
        row = conn.execute("SELECT * FROM problems WHERE id = ?", (pid,)).fetchone()
    except Exception:
        row = None
    conn.close()
    if row is None:
        return None
    return dict(row)

def get_all_problems() -> list[dict]:
    """Retrieve all problems stored in SQLite."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM problems ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ── Solution CRUD ────────────────────────────────────────

def insert_solution(problem_id: int, startup_name: str, filename: str,
                    raw_text: str, solution_json: dict,
                    eligible: bool, eligibility_reason: str,
                    consistency_flags: list) -> int:
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO solutions
           (problem_id, startup_name, filename, raw_text, solution_json,
            eligible, eligibility_reason, consistency_flags)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (problem_id, startup_name, filename, raw_text,
         json.dumps(solution_json), int(eligible), eligibility_reason,
         json.dumps(consistency_flags))
    )
    sid = cur.lastrowid
    conn.commit()
    conn.close()
    return sid

def get_solutions_for_problem(problem_id, eligible_only: bool = True) -> list[dict]:
    conn = get_connection()
    pid = int(problem_id) if str(problem_id).isdigit() else problem_id
    query = "SELECT * FROM solutions WHERE problem_id = ?"
    if eligible_only:
        query += " AND eligible = 1"
    rows = conn.execute(query, (pid,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_solution(solution_id: int) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM solutions WHERE id = ?", (solution_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)

# ── Score CRUD ───────────────────────────────────────────

def insert_score(solution_id: int, problem_id: int, scores: dict,
                 justification: dict, final_score: float) -> int:
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO scores
           (solution_id, problem_id, relevance, feasibility, innovation,
            team_credibility, pilot_readiness, justification_json, final_score, scores_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (solution_id, problem_id,
         scores.get("technical_fit", scores.get("relevance", 0)),
         scores.get("feasibility", 0),
         scores.get("innovation", 0),
         scores.get("team_capability", scores.get("team_credibility", 0)),
         scores.get("feasibility", scores.get("pilot_readiness", 0)),
         json.dumps(justification), final_score, json.dumps(scores))
    )
    sid = cur.lastrowid
    conn.commit()
    conn.close()
    return sid

def get_scores_for_problem(problem_id) -> list[dict]:
    conn = get_connection()
    pid = int(problem_id) if str(problem_id).isdigit() else problem_id
    rows = conn.execute(
        """SELECT sc.*, s.startup_name, s.filename, s.consistency_flags
           FROM scores sc
           JOIN solutions s ON sc.solution_id = s.id
           WHERE sc.problem_id = ?
           ORDER BY sc.final_score DESC""",
        (pid,)
    ).fetchall()
    conn.close()
    output = []
    for r in rows:
        item = dict(r)
        if item.get("scores_json"):
            try:
                parsed = json.loads(item["scores_json"])
                item.update(parsed)
            except Exception:
                pass
        output.append(item)
    return output

def delete_scores_for_problem(problem_id):
    """Clear existing scores before re-scoring."""
    conn = get_connection()
    pid = int(problem_id) if str(problem_id).isdigit() else problem_id
    conn.execute("DELETE FROM scores WHERE problem_id = ?", (pid,))
    conn.commit()
    conn.close()
