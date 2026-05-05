import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'campus_trade.db')


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript('''
    PRAGMA foreign_keys = ON;

    DROP TABLE IF EXISTS Orders;
    DROP TABLE IF EXISTS Item;
    DROP TABLE IF EXISTS User;
    DROP VIEW IF EXISTS SoldItemsView;
    DROP VIEW IF EXISTS UnsoldItemsView;

    CREATE TABLE User (
        user_id TEXT PRIMARY KEY,
        user_name TEXT NOT NULL,
        phone TEXT NOT NULL
    );

    CREATE TABLE Item (
        item_id TEXT PRIMARY KEY,
        item_name TEXT NOT NULL,
        category TEXT NOT NULL,
        price REAL NOT NULL CHECK(price >= 0),
        status INTEGER NOT NULL DEFAULT 0 CHECK(status IN (0, 1)),
        seller_id TEXT NOT NULL,
        FOREIGN KEY (seller_id) REFERENCES User(user_id)
    );

    CREATE TABLE Orders (
        order_id TEXT PRIMARY KEY,
        item_id TEXT NOT NULL UNIQUE,
        buyer_id TEXT NOT NULL,
        order_date TEXT NOT NULL,
        FOREIGN KEY (item_id) REFERENCES Item(item_id),
        FOREIGN KEY (buyer_id) REFERENCES User(user_id)
    );

    CREATE TRIGGER check_item_status_before_insert_order
    BEFORE INSERT ON Orders
    BEGIN
        SELECT CASE
            WHEN (SELECT status FROM Item WHERE item_id = NEW.item_id) != 1 THEN
                RAISE(ABORT, 'Item must have status=1 before creating order')
        END;
    END;

    CREATE TRIGGER check_item_status_before_update_order
    BEFORE UPDATE ON Orders
    BEGIN
        SELECT CASE
            WHEN (SELECT status FROM Item WHERE item_id = NEW.item_id) != 1 THEN
                RAISE(ABORT, 'Item must have status=1 before creating order')
        END;
    END;

    INSERT INTO User (user_id, user_name, phone) VALUES
        ('u001', 'ZhangSan', '13800000001'),
        ('u002', 'LiSi', '13800000002'),
        ('u003', 'WangWu', '13800000003'),
        ('u004', 'ZhaoLiu', '13800000004');

    INSERT INTO Item (item_id, item_name, category, price, status, seller_id) VALUES
        ('i001', 'CalculusBook', 'Book', 20, 0, 'u001'),
        ('i002', 'DeskLamp', 'DailyGoods', 35, 1, 'u002'),
        ('i003', 'Microcontroller', 'Electronics', 80, 0, 'u001'),
        ('i004', 'Chair', 'Furniture', 50, 1, 'u003'),
        ('i005', 'WaterBottle', 'DailyGoods', 15, 0, 'u004');

    INSERT INTO Orders (order_id, item_id, buyer_id, order_date) VALUES
        ('o001', 'i002', 'u001', '2024-05-01'),
        ('o002', 'i004', 'u002', '2024-05-03');

    CREATE VIEW SoldItemsView AS
    SELECT i.item_name, o.buyer_id
    FROM Item i
    JOIN Orders o ON i.item_id = o.item_id;

    CREATE VIEW UnsoldItemsView AS
    SELECT item_id, item_name, category, price, seller_id
    FROM Item
    WHERE status = 0;
    ''')

    conn.commit()
    conn.close()


if __name__ == '__main__':
    init_database()
    print('Database initialized successfully.')
