import sqlite3
import os
from datetime import datetime, date
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "ledger.db")


def _get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            sort_order INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            category_id INTEGER REFERENCES categories(id),
            image_path TEXT,
            thumb_path TEXT,
            note TEXT,
            stock INTEGER DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL REFERENCES items(id),
            item_name TEXT NOT NULL,
            price REAL NOT NULL,
            quantity INTEGER DEFAULT 1,
            sale_date TEXT NOT NULL DEFAULT (date('now','localtime')),
            sale_time TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            payment_method TEXT DEFAULT '现金',
            note TEXT
        );

        INSERT OR IGNORE INTO categories (name, sort_order) VALUES
            ('耳饰', 1), ('项链', 2), ('手链', 3), ('戒指', 4),
            ('发饰', 5), ('胸针', 6), ('其他', 99);
    """)
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
#  Items (catalog)
# ---------------------------------------------------------------------------

def add_item(name, price, category_id, image_path="", thumb_path="", note="", stock=1):
    conn = _get_conn()
    cur = conn.execute(
        "INSERT INTO items (name, price, category_id, image_path, thumb_path, note, stock) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (name, price, category_id, image_path, thumb_path, note, stock))
    conn.commit()
    item_id = cur.lastrowid
    conn.close()
    return item_id


def update_item(item_id, name, price, category_id, note="", stock=1):
    conn = _get_conn()
    conn.execute(
        "UPDATE items SET name=?, price=?, category_id=?, note=?, stock=? WHERE id=?",
        (name, price, category_id, note, stock, item_id))
    conn.commit()
    conn.close()


def update_item_image(item_id, image_path, thumb_path):
    conn = _get_conn()
    conn.execute(
        "UPDATE items SET image_path=?, thumb_path=? WHERE id=?",
        (image_path, thumb_path, item_id))
    conn.commit()
    conn.close()


def delete_item(item_id):
    conn = _get_conn()
    row = conn.execute("SELECT image_path, thumb_path FROM items WHERE id=?", (item_id,)).fetchone()
    if not row:
        conn.close()
        return None
    conn.execute("DELETE FROM sales WHERE item_id=?", (item_id,))
    conn.execute("DELETE FROM items WHERE id=?", (item_id,))
    conn.commit()
    conn.close()
    return {"image_path": row["image_path"], "thumb_path": row["thumb_path"]}


def get_all_items():
    conn = _get_conn()
    rows = conn.execute("""
        SELECT i.*, c.name AS category_name
        FROM items i
        LEFT JOIN categories c ON i.category_id = c.id
        ORDER BY c.sort_order, i.name
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_item(item_id):
    conn = _get_conn()
    row = conn.execute("""
        SELECT i.*, c.name AS category_name
        FROM items i
        LEFT JOIN categories c ON i.category_id = c.id
        WHERE i.id=?
    """, (item_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def search_items(query):
    conn = _get_conn()
    rows = conn.execute("""
        SELECT i.*, c.name AS category_name
        FROM items i
        LEFT JOIN categories c ON i.category_id = c.id
        WHERE i.name LIKE ? OR i.note LIKE ?
        ORDER BY c.sort_order, i.name
    """, (f"%{query}%", f"%{query}%")).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
#  Categories
# ---------------------------------------------------------------------------

def get_categories():
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM categories ORDER BY sort_order").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_category(name):
    conn = _get_conn()
    cur = conn.execute("INSERT INTO categories (name) VALUES (?)", (name,))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


# ---------------------------------------------------------------------------
#  Sales
# ---------------------------------------------------------------------------

def record_sale(item_id, item_name, price, quantity=1, payment_method="现金", note=""):
    conn = _get_conn()
    cur = conn.execute(
        "INSERT INTO sales (item_id, item_name, price, quantity, payment_method, note) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (item_id, item_name, price, quantity, payment_method, note))
    conn.commit()
    sale_id = cur.lastrowid
    conn.close()
    return sale_id


def get_sales(sale_date=None, limit=200):
    conn = _get_conn()
    if sale_date:
        rows = conn.execute("""
            SELECT s.*, i.image_path, i.thumb_path
            FROM sales s
            LEFT JOIN items i ON s.item_id = i.id
            WHERE s.sale_date = ?
            ORDER BY s.sale_time DESC
        """, (sale_date,)).fetchall()
    else:
        rows = conn.execute("""
            SELECT s.*, i.image_path, i.thumb_path
            FROM sales s
            LEFT JOIN items i ON s.item_id = i.id
            ORDER BY s.sale_time DESC
            LIMIT ?
        """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_today_summary():
    today = date.today().isoformat()
    conn = _get_conn()
    row = conn.execute("""
        SELECT COUNT(*) AS count, COALESCE(SUM(price * quantity), 0) AS total
        FROM sales WHERE sale_date = ?
    """, (today,)).fetchone()
    conn.close()
    return {"date": today, "count": row["count"], "total": round(row["total"], 2)}


def get_recent_sales(limit=20):
    return get_sales(limit=limit)


def get_sales_range(start_date, end_date):
    conn = _get_conn()
    rows = conn.execute("""
        SELECT s.*, i.image_path, i.thumb_path
        FROM sales s
        LEFT JOIN items i ON s.item_id = i.id
        WHERE s.sale_date >= ? AND s.sale_date <= ?
        ORDER BY s.sale_time DESC
    """, (start_date, end_date)).fetchall()
    conn.close()
    return [dict(r) for r in rows]
