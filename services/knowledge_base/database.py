import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from config import DATABASE_PATH


def get_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    # 启用 WAL 模式提升并发性能
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_database():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute("PRAGMA table_info(chat_history)")
    columns = {row[1] for row in cursor.fetchall()}

    if not columns:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                intent_code INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
    elif 'user_id' not in columns and 'phone_number' in columns:
        cursor.execute('ALTER TABLE chat_history ADD COLUMN user_id INTEGER REFERENCES users(id)')
        cursor.execute('UPDATE chat_history SET user_id = 0 WHERE user_id IS NULL')

    cursor.execute("PRAGMA table_info(user_info)")
    ui_columns = {row[1] for row in cursor.fetchall()}

    if not ui_columns:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_info (
                user_id INTEGER PRIMARY KEY,
                name TEXT,
                intent_preference INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
    elif 'user_id' not in ui_columns and 'phone_number' in ui_columns:
        cursor.execute('ALTER TABLE user_info ADD COLUMN user_id INTEGER REFERENCES users(id)')
        cursor.execute("UPDATE user_info SET user_id = CAST(phone_number AS INTEGER) WHERE user_id IS NULL")

    conn.commit()
    conn.close()


def register_user(username, password):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'INSERT INTO users (username, password_hash) VALUES (?, ?)',
            (username, generate_password_hash(password))
        )
        conn.commit()
        user_id = cursor.lastrowid
        return {"success": True, "user_id": user_id, "username": username}
    except sqlite3.IntegrityError:
        return {"success": False, "error": "用户名已存在"}
    finally:
        conn.close()


def login_user(username, password):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    conn.close()
    if user and check_password_hash(user["password_hash"], password):
        return {"success": True, "user_id": user["id"], "username": user["username"]}
    return {"success": False, "error": "用户名或密码错误"}


def get_user_by_id(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, username, created_at FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None


def fetch_chat_history(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT role, content, intent_code, created_at FROM chat_history WHERE user_id = ? ORDER BY created_at',
        (user_id,)
    )
    history = cursor.fetchall()
    conn.close()
    return [
        {
            "role": row["role"],
            "content": row["content"],
            "intent_code": row["intent_code"],
            "created_at": row["created_at"],
        }
        for row in history
    ]


def save_chat_message(user_id, role, content, intent_code=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO chat_history (user_id, role, content, intent_code) VALUES (?, ?, ?, ?)',
        (user_id, role, content, intent_code)
    )
    conn.commit()
    conn.close()


def get_user_info(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM user_info WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    if user:
        return dict(user)
    return None


def update_user_info(user_id, name=None, intent_preference=None):
    conn = get_connection()
    cursor = conn.cursor()
    existing = get_user_info(user_id)
    if existing:
        updates = []
        params = []
        if name:
            updates.append("name = ?")
            params.append(name)
        if intent_preference is not None:
            updates.append("intent_preference = ?")
            params.append(intent_preference)
        updates.append("updated_at = ?")
        params.append(datetime.now().isoformat())
        params.append(user_id)
        cursor.execute(f'UPDATE user_info SET {", ".join(updates)} WHERE user_id = ?', params)
    else:
        cursor.execute(
            'INSERT INTO user_info (user_id, name, intent_preference) VALUES (?, ?, ?)',
            (user_id, name, intent_preference or 0)
        )
    conn.commit()
    conn.close()


def get_user_stats(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT intent_code, COUNT(*) as count FROM chat_history WHERE user_id = ? GROUP BY intent_code',
        (user_id,)
    )
    stats = cursor.fetchall()
    conn.close()
    return {row["intent_code"]: row["count"] for row in stats}
