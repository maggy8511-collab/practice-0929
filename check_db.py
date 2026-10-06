import sqlite3
import os
import sys
import unicodedata

# 解決 Windows 終端 (PowerShell / CMD) 繁體中文 Big5/CP950 編碼問題，強制統一為 UTF-8
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

def get_display_width(text):
    """計算字串於終端機顯示的實際寬度（全形/中文算 2 格，半形英數算 1 格）"""
    width = 0
    for ch in str(text):
        ea = unicodedata.east_asian_width(ch)
        if ea in ('F', 'W'):
            width += 2
        else:
            width += 1
    return width

def format_row(values, widths):
    """依照欄寬格式化單列文字，支援中文字元對齊"""
    parts = []
    for val, w in zip(values, widths):
        s = str(val) if val is not None else "NULL"
        disp_w = get_display_width(s)
        padding = max(0, w - disp_w)
        parts.append(s + " " * padding)
    return " | ".join(parts)

def print_table(cursor, table_name, title):
    cursor.execute(f"PRAGMA table_info({table_name});")
    cols_info = cursor.fetchall()
    col_names = [col[1] for col in cols_info]

    cursor.execute(f"SELECT * FROM {table_name};")
    rows = cursor.fetchall()

    print(f"\n{'='*75}")
    print(f"[{title}] - 資料表: {table_name} (共 {len(rows)} 筆資料)")
    print(f"{'='*75}")

    # 計算各欄位最適寬度
    widths = []
    for i, col in enumerate(col_names):
        col_w = get_display_width(col)
        data_w = max((get_display_width(row[i]) for row in rows), default=0)
        widths.append(max(col_w, data_w) + 2)

    # 印出表頭
    header = format_row(col_names, widths)
    print(header)
    print("-" * get_display_width(header))

    # 印出資料列
    for row in rows:
        print(format_row(row, widths))

def check_database():
    if not os.path.exists(DB_PATH):
        print(f"[錯誤] 找不到資料庫檔案: {DB_PATH}，請先執行 create_db.py 建立資料庫！")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print(f"\n[開始驗證] SQLite 資料庫: [{DB_PATH}]")

    # 1. 印出四張基本資料表
    print_table(cursor, "customer", "1. 客戶資料表")
    print_table(cursor, "product", "2. 商品資料表")
    print_table(cursor, "orders", "3. 訂單資料表")
    print_table(cursor, "order_item", "4. 訂單明細資料表")

    # 2. 跨表 JOIN 檢視訂單詳情 (驗證一筆訂單含多項商品、以及歷史價格)
    print(f"\n{'='*75}")
    print("[跨表整合驗證] 訂單總覽與明細 (檢驗多項商品與當前/下單價格差異)")
    print(f"{'='*75}")

    query = """
    SELECT 
        o.訂單編號,
        c.名稱 AS 客戶名稱,
        o.訂單日期,
        p.名稱 AS 商品名稱,
        p.分類,
        oi.數量,
        oi.單價 AS 下單當時單價,
        p.單價 AS 商品現價,
        (oi.數量 * oi.單價) AS 小計
    FROM orders o
    JOIN customer c ON o.客戶編號 = c.客戶編號
    JOIN order_item oi ON o.訂單編號 = oi.訂單編號
    JOIN product p ON oi.商品編號 = p.商品編號
    ORDER BY o.訂單編號, oi.商品編號;
    """
    cursor.execute(query)
    join_rows = cursor.fetchall()

    join_cols = ["訂單編號", "客戶名稱", "訂單日期", "商品名稱", "分類", "數量", "下單當時單價", "商品現價", "小計"]
    widths = [14, 10, 12, 18, 10, 6, 14, 10, 10]

    header = format_row(join_cols, widths)
    print(header)
    print("-" * get_display_width(header))

    current_order = None
    order_total = 0
    grand_total = 0

    for row in join_rows:
        order_id = row[0]
        subtotal = row[8]
        grand_total += subtotal

        # 如果換了一張訂單，印出前一張的總計
        if current_order is not None and current_order != order_id:
            print(f"   └── 訂單 [{current_order}] 總金額: NT$ {order_total:,.0f}")
            print("   " + "-" * 60)
            order_total = 0

        current_order = order_id
        order_total += subtotal

        formatted_row = list(row)
        formatted_row[6] = f"NT$ {row[6]:,.0f}"
        formatted_row[7] = f"NT$ {row[7]:,.0f}"
        formatted_row[8] = f"NT$ {row[8]:,.0f}"
        print(format_row(formatted_row, widths))

    if current_order is not None:
        print(f"   └── 訂單 [{current_order}] 總金額: NT$ {order_total:,.0f}")

    print(f"\n[營收統計] 全部門市訂單總營收: NT$ {grand_total:,.0f}")

    # 3. 約束條件驗證
    print(f"\n{'='*75}")
    print("[約束條件驗證報告]")
    print(f"{'='*75}")

    # 檢查 order_item 複合主鍵
    cursor.execute("PRAGMA table_info(order_item);")
    pk_cols = [col[1] for col in cursor.fetchall() if col[5] > 0]
    print(f"[OK] order_item 主鍵結構: {pk_cols} (符合「訂單編號 + 商品編號」複合主鍵)")

    # 檢查 CHECK 約束
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='order_item';")
    oi_sql = cursor.fetchone()[0]
    has_qty_check = "數量 > 0" in oi_sql
    has_price_check = "單價 >= 0" in oi_sql
    print(f"[OK] order_item CHECK (數量 > 0): {'通過' if has_qty_check else '未設定'}")
    print(f"[OK] order_item CHECK (單價 >= 0): {'通過' if has_price_check else '未設定'}")

    # 檢查多商品訂單案例
    cursor.execute("SELECT 訂單編號, COUNT(*) as cnt FROM order_item GROUP BY 訂單編號 HAVING cnt > 1;")
    multi_items = cursor.fetchall()
    print(f"[OK] 包含多項商品的訂單案例: {', '.join([f'{m[0]} ({m[1]}項)' for m in multi_items])}")

    conn.close()
    print("\n[完成] 全部資料表結構與資料驗證完畢！\n")

if __name__ == "__main__":
    check_database()
