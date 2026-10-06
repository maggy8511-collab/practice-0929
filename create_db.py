import sqlite3
import os
import sys
from werkzeug.security import generate_password_hash

# 解決 Windows 終端編碼問題
if sys.platform.startswith('win'):
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except Exception:
        pass
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

DB_PATH = "orders.db"

def init_database():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")

    # 1. 客戶資料表 customer(客戶編號 PK、名稱、電話、地址)
    cursor.execute("""
    CREATE TABLE customer (
        客戶編號 TEXT PRIMARY KEY,
        名稱 TEXT NOT NULL,
        電話 TEXT,
        地址 TEXT
    );
    """)

    # 2. 商品資料表 product(商品編號 PK、名稱、單價、庫存、分類)
    cursor.execute("""
    CREATE TABLE product (
        商品編號 TEXT PRIMARY KEY,
        名稱 TEXT NOT NULL,
        單價 REAL NOT NULL CHECK (單價 >= 0),
        庫存 INTEGER NOT NULL CHECK (庫存 >= 0),
        分類 TEXT NOT NULL
    );
    """)

    # 3. 訂單資料表 orders(訂單編號 PK、客戶編號 FK、訂單日期、狀態、業務人員)
    cursor.execute("""
    CREATE TABLE orders (
        訂單編號 TEXT PRIMARY KEY,
        客戶編號 TEXT NOT NULL,
        訂單日期 TEXT NOT NULL,
        狀態 TEXT NOT NULL CHECK (狀態 IN ('處理中', '已出貨', '已完成', '已取消')),
        業務人員 TEXT NOT NULL,
        FOREIGN KEY (客戶編號) REFERENCES customer(客戶編號) ON UPDATE CASCADE ON DELETE RESTRICT
    );
    """)

    # 4. 訂單明細資料表 order_item(訂單編號 FK、商品編號 FK、數量、單價), 複合主鍵
    cursor.execute("""
    CREATE TABLE order_item (
        訂單編號 TEXT NOT NULL,
        商品編號 TEXT NOT NULL,
        數量 INTEGER NOT NULL CHECK (數量 > 0),
        單價 REAL NOT NULL CHECK (單價 >= 0),
        PRIMARY KEY (訂單編號, 商品編號),
        FOREIGN KEY (訂單編號) REFERENCES orders(訂單編號) ON UPDATE CASCADE ON DELETE CASCADE,
        FOREIGN KEY (商品編號) REFERENCES product(商品編號) ON UPDATE CASCADE ON DELETE RESTRICT
    );
    """)

    # 5. 管理者帳號資料表 users
    cursor.execute("""
    CREATE TABLE users (
        username TEXT PRIMARY KEY,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'admin'
    );
    """)

    # ==================== 插入 5 筆繁體中文測試資料 ====================

    # 管理者帳號 (admin / admin123)
    admin_hash = generate_password_hash("admin123")
    cursor.execute("INSERT INTO users VALUES (?, ?, ?);", ("admin", admin_hash, "admin"))

    # 客戶 5 筆
    customers = [
        ("C001", "陳大明", "0912-345-678", "台北市大安區信義路三段 100 號"),
        ("C002", "林小美", "0928-111-222", "新北市板橋區縣民大道二段 50 號"),
        ("C003", "黃國華", "0933-888-999", "台中市西屯區台灣大道三段 99 號"),
        ("C004", "張雅婷", "0955-666-777", "台南市東區中華東路一段 88 號"),
        ("C005", "許家豪", "0970-222-333", "高雄市苓雅區四維三路 2 號")
    ]
    cursor.executemany("INSERT INTO customer VALUES (?, ?, ?, ?);", customers)

    # 商品 5 筆
    products = [
        ("P001", "輕薄筆記型電腦", 32000.0, 25, "3C電子"),
        ("P002", "無線機械鍵盤", 2490.0, 80, "電腦周邊"),
        ("P003", "人體工學滑鼠", 1290.0, 150, "電腦周邊"),
        ("P004", "27吋 4K電競螢幕", 10800.0, 40, "顯示設備"),
        ("P005", "降噪藍牙耳機", 4500.0, 60, "音訊設備")
    ]
    cursor.executemany("INSERT INTO product VALUES (?, ?, ?, ?, ?);", products)

    # 訂單 5 筆 (狀態: 處理中 / 已出貨 / 已完成 / 已取消)
    orders = [
        ("ORD-20260301", "C001", "2026-03-01", "已完成", "王志強"),
        ("ORD-20260302", "C002", "2026-03-05", "已出貨", "李美玲"),
        ("ORD-20260303", "C003", "2026-03-10", "處理中", "王志強"),
        ("ORD-20260304", "C004", "2026-03-15", "已出貨", "張建國"),
        ("ORD-20260305", "C005", "2026-03-20", "處理中", "李美玲")
    ]
    cursor.executemany("INSERT INTO orders VALUES (?, ?, ?, ?, ?);", orders)

    # 訂單明細 (多商品案例，保存下單歷史價格)
    order_items = [
        ("ORD-20260301", "P001", 1, 31000.0),  # 下單當時促銷價 31000 (現價 32000)
        ("ORD-20260301", "P003", 2, 1290.0),
        ("ORD-20260302", "P002", 1, 2490.0),
        ("ORD-20260302", "P005", 1, 4500.0),
        ("ORD-20260303", "P004", 2, 10800.0),
        ("ORD-20260304", "P001", 1, 32000.0),
        ("ORD-20260304", "P002", 2, 2300.0),   # 下單當時促銷價 2300 (現價 2490)
        ("ORD-20260304", "P003", 1, 1290.0),
        ("ORD-20260305", "P004", 1, 10800.0)
    ]
    cursor.executemany("INSERT INTO order_item VALUES (?, ?, ?, ?);", order_items)

    conn.commit()
    conn.close()
    print("[成功] orders.db 資料庫初始化完畢，已建立 4 張資料表與管理員帳號！")

if __name__ == "__main__":
    init_database()
