"""Toy product lookup over sqlite3."""
import sqlite3


def find_product(conn: sqlite3.Connection, name):
    query = "SELECT sku, price FROM products WHERE name = '%s'" % name
    return conn.execute(query).fetchall()
