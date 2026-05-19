import os
import threading
import time
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_DSN = os.getenv(
    "DATABASE_DSN",
    "host=crdb-1,crdb-2,crdb-3 port=26257,26257,26257 dbname=observability_demo user=root sslmode=disable connect_timeout=3",
)


def connect():
    return psycopg2.connect(DATABASE_DSN)


def healthcheck() -> bool:
    with connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
            return cursor.fetchone()[0] == 1


def get_products() -> list[dict[str, Any]]:
    with connect() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT id, name, price_cents, stock FROM products ORDER BY id")
            return [dict(row) for row in cursor.fetchall()]


def get_orders(limit: int = 10) -> list[dict[str, Any]]:
    with connect() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                "SELECT id, total_cents, created_at FROM orders ORDER BY created_at DESC LIMIT %s",
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]


def create_order(product_id: int) -> dict[str, Any]:
    with connect() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                "SELECT id, name, price_cents FROM products WHERE id = %s",
                (product_id,),
            )
            product = cursor.fetchone()
            if product is None:
                raise ValueError(f"unknown product_id={product_id}")
            cursor.execute(
                "INSERT INTO orders (total_cents) VALUES (%s) RETURNING id, total_cents, created_at",
                (product["price_cents"],),
            )
            order = dict(cursor.fetchone())
            conn.commit()
            order["product"] = dict(product)
            return order


def slow_query(seconds: float) -> dict[str, Any]:
    start = time.perf_counter()
    with connect() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT count(*) AS product_count FROM products")
            row = dict(cursor.fetchone())
            time.sleep(seconds)
    row["simulated_db_wait_seconds"] = seconds
    row["elapsed_seconds"] = round(time.perf_counter() - start, 3)
    return row


def hold_connections(count: int, seconds: float) -> int:
    count = max(1, min(count, 100))
    seconds = max(1, min(seconds, 120))

    def worker() -> None:
        conn = None
        try:
            conn = connect()
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
                time.sleep(seconds)
        finally:
            if conn is not None:
                conn.close()

    for _ in range(count):
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
    return count
