####
# File: database.py 
# Author: Joey Johnson 
# Desc: Sets up and makes the current relational database schema
#
####

from pathlib import Path 
import sqlite3 # https://www.sqlite.org/ 
import secrets 

# variables to change or modify as time goes on. 
databaseFile = "clockify.db" 

EXPECTED = {
    "users", "categories", "activities", "goals", "entries",
    "breaks", "tags", "entry_tags", "entry_durations",
}

# SCHEMA
SCHEMA = """
-- user id is a random number generated in python (see create_user)
CREATE TABLE IF NOT EXISTS users (
    user_id     INTEGER PRIMARY KEY,
    username    TEXT NOT NULL UNIQUE,
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS categories (
    category_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    name        TEXT NOT NULL,
    color       TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- category contains activities (1:N)
CREATE TABLE IF NOT EXISTS activities (
    activity_id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL,
    name        TEXT NOT NULL,
    description TEXT,
    FOREIGN KEY (category_id) REFERENCES categories(category_id) ON DELETE CASCADE
);

-- user sets goals (1:N), goal is towards a category (N:1)
CREATE TABLE IF NOT EXISTS goals (
    goal_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id        INTEGER NOT NULL,
    category_id    INTEGER NOT NULL,
    target_minutes INTEGER NOT NULL CHECK (target_minutes > 0),
    start_date     TEXT NOT NULL,
    end_date       TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES categories(category_id) ON DELETE CASCADE
);

-- user logs entries (1:N), entry tracks an activity (N:1)
-- duration is derived from start/end, so it's not stored
CREATE TABLE IF NOT EXISTS entries (
    entry_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    activity_id INTEGER NOT NULL,
    start_time  TEXT NOT NULL,
    end_time    TEXT,
    notes       TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (activity_id) REFERENCES activities(activity_id) ON DELETE CASCADE
);

-- entry has breaks (1:N)
CREATE TABLE IF NOT EXISTS breaks (
    break_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id    INTEGER NOT NULL,
    start_time  TEXT NOT NULL,
    end_time    TEXT,
    FOREIGN KEY (entry_id) REFERENCES entries(entry_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS tags (
    tag_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    label   TEXT NOT NULL,
    UNIQUE (user_id, label),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- entries <-> tags is many-to-many, needs a junction table
CREATE TABLE IF NOT EXISTS entry_tags (
    entry_id INTEGER NOT NULL,
    tag_id   INTEGER NOT NULL,
    PRIMARY KEY (entry_id, tag_id),
    FOREIGN KEY (entry_id) REFERENCES entries(entry_id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(tag_id) ON DELETE CASCADE
);

-- duration computed on read, in minutes
CREATE VIEW IF NOT EXISTS entry_durations AS
SELECT
    entry_id,
    user_id,
    activity_id,
    start_time,
    end_time,
    ROUND((julianday(end_time) - julianday(start_time)) * 1440, 2) AS duration_minutes
FROM entries
WHERE end_time IS NOT NULL;
"""

# check to see if the database file exists first.
target_file = Path(__file__).resolve().parent / databaseFile

# if target_file.is_file():
#     print("Clockify database.db not formed, already exists")
# else: 
#     try: 
#         conn = sqlite3.connect(databaseFile)
#         print("Clockify database.db formed")
#     except:
#         print("Clockify database.db not formed")

def get_connection():
    conn = sqlite3.connect(target_file)
    conn.execute("PRAGMA foreign_keys = ON;")  # sqlite ignores FKs unless set per connection
    return conn


def get_existing_tables(conn):
    # sqlite_master is sqlite's internal catalog of every table/view/index
    rows = conn.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {row[0] for row in rows}


def generate_user_id():
    # random positive 63-bit int, fits sqlite INTEGER, not sequential/guessable
    return secrets.randbits(63) or 1


def create_user(conn, username, max_tries=5):
    for _ in range(max_tries):
        user_id = generate_user_id()
        try:
            conn.execute(
                "INSERT INTO users (user_id, username) VALUES (?, ?)",
                (user_id, username),
            )
            conn.commit()
            return user_id
        except sqlite3.IntegrityError as e:
            if "username" in str(e):
                raise ValueError(f"username '{username}' already taken")
            # otherwise it was an id collision (basically never), retry
    raise RuntimeError("could not generate a unique user id")


def init_db():
    existed = target_file.is_file()
    conn = None
    try:
        conn = get_connection()

        before = get_existing_tables(conn)
        missing = EXPECTED - before

        if not missing:
            print(f"{databaseFile}: all tables present, nothing to do")
            return

        # IF NOT EXISTS means only the missing ones actually get created
        conn.executescript(SCHEMA)
        conn.commit()

        after = get_existing_tables(conn)
        added = sorted(after - before)
        still_missing = sorted(EXPECTED - after)

        if not existed:
            print(f"{databaseFile} created")
        print(f"added: {', '.join(added) if added else 'none'}")
        if still_missing:
            print(f"WARNING still missing: {', '.join(still_missing)}")
    except sqlite3.Error as e:
        print(f"{databaseFile} setup failed: {e}")
    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    init_db()
                
