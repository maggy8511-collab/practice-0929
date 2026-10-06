import os
import sys
import io
import base64
import sqlite3
import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from werkzeug.security import generate_password_hash, check_password_hash
import qrcode

# 確保 Windows 主控台編碼支援 UTF-8
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

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "orderhub-super-secret-key-2026")

DB_PATH = "orders.db"

def init_db_if_not_exists():
    if not os.path.exists(DB_PATH):
        try:
            from create_db import init_database
            init_database()
        except Exception as e:
            print(f"初始化資料庫失敗: {e}")

init_db_if_not_exists()

def get_db():
    init_db_if_not_exists()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

# ==================== 權限驗證裝飾器 ====================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user" not in session:
            flash("請先登入管理員帳號！", "warning")
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return decorated_function

# ==================== QR Code 產生工具 ====================
def generate_qr_code(data_text):
    """將文字或網址轉換為 Base64 PNG 圖片 Data URL"""
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=6,
            border=2,
        )
        qr.add_data(data_text)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#0f172a", back_color="#ffffff")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception as e:
        print(f"QRCode 產生失敗: {e}")
        return None

# ==================== 登入 / 登出 ====================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()

        if user and check_password_hash(user["password_hash"], password):
            session["user"] = username
            flash(f"歡迎回來，管理員 {username}！", "success")
            next_page = request.args.get("next")
            return redirect(next_page or url_for("dashboard"))
        else:
            flash("帳號或密碼錯誤，請重新輸入！(預設: admin / admin123)", "error")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("已成功登出系統！", "info")
    return redirect(url_for("login"))

# ==================== 首頁與儀表板 ====================
@app.route("/")
def index():
    if "user" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_db()
    # 統計數據
    total_orders = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    total_revenue = conn.execute("SELECT COALESCE(SUM(數量 * 單價), 0) FROM order_item").fetchone()[0]
    total_customers = conn.execute("SELECT COUNT(*) FROM customer").fetchone()[0]
    total_products = conn.execute("SELECT COUNT(*) FROM product").fetchone()[0]

    # 近期 5 筆訂單
    recent_orders = conn.execute("""
        SELECT o.訂單編號, o.訂單日期, o.狀態, o.業務人員,
               c.名稱 AS 客戶名稱,
               COALESCE(SUM(oi.數量 * oi.單價), 0) AS 總金額
        FROM orders o
        JOIN customer c ON o.客戶編號 = c.客戶編號
        LEFT JOIN order_item oi ON o.訂單編號 = oi.訂單編號
        GROUP BY o.訂單編號
        ORDER BY o.訂單日期 DESC, o.訂單編號 DESC
        LIMIT 5;
    """).fetchall()
    conn.close()

    stats = {
        "total_orders": total_orders,
        "total_revenue": total_revenue,
        "total_customers": total_customers,
        "total_products": total_products
    }
    return render_template("dashboard.html", stats=stats, recent_orders=recent_orders)

# ==================== 客戶管理 ====================
@app.route("/customers")
@login_required
def list_customers():
    conn = get_db()
    customers = conn.execute("SELECT * FROM customer ORDER BY 客戶編號").fetchall()
    conn.close()
    return render_template("customers.html", customers=customers)

@app.route("/customer/new", methods=["POST"])
@login_required
def add_customer():
    customer_id = request.form.get("customer_id", "").strip().upper()
    name = request.form.get("name", "").strip()
    phone = request.form.get("phone", "").strip()
    address = request.form.get("address", "").strip()

    if not customer_id or not name:
        flash("客戶編號與名稱為必填欄位！", "error")
        return redirect(url_for("list_customers"))

    conn = get_db()
    try:
        conn.execute("INSERT INTO customer (客戶編號, 名稱, 電話, 地址) VALUES (?, ?, ?, ?)",
                     (customer_id, name, phone, address))
        conn.commit()
        flash(f"客戶 [{name}] 已成功建立！", "success")
    except sqlite3.IntegrityError:
        flash(f"建立失敗：客戶編號 [{customer_id}] 已存在！", "error")
    finally:
        conn.close()

    return redirect(url_for("list_customers"))

@app.route("/customer/edit/<customer_id>", methods=["POST"])
@login_required
def edit_customer(customer_id):
    name = request.form.get("name", "").strip()
    phone = request.form.get("phone", "").strip()
    address = request.form.get("address", "").strip()

    conn = get_db()
    conn.execute("UPDATE customer SET 名稱 = ?, 電話 = ?, 地址 = ? WHERE 客戶編號 = ?",
                 (name, phone, address, customer_id))
    conn.commit()
    conn.close()
    flash(f"客戶 [{customer_id}] 資料已更新完成！", "success")
    return redirect(url_for("list_customers"))

@app.route("/customer/delete/<customer_id>", methods=["POST"])
@login_required
def delete_customer(customer_id):
    conn = get_db()
    try:
        conn.execute("DELETE FROM customer WHERE 客戶編號 = ?", (customer_id,))
        conn.commit()
        flash("客戶資料已刪除！", "info")
    except sqlite3.IntegrityError:
        flash("無法刪除：該客戶已有訂單關聯，無法直接移除！", "error")
    finally:
        conn.close()
    return redirect(url_for("list_customers"))

# ==================== 商品管理 ====================
@app.route("/products")
@login_required
def list_products():
    conn = get_db()
    products = conn.execute("SELECT * FROM product ORDER BY 商品編號").fetchall()
    conn.close()
    return render_template("products.html", products=products)

@app.route("/product/new", methods=["POST"])
@login_required
def add_product():
    product_id = request.form.get("product_id", "").strip().upper()
    name = request.form.get("name", "").strip()
    price = float(request.form.get("price", 0))
    stock = int(request.form.get("stock", 0))
    category = request.form.get("category", "").strip()

    if price < 0 or stock < 0:
        flash("單價或庫存不可為負數！", "error")
        return redirect(url_for("list_products"))

    conn = get_db()
    try:
        conn.execute("INSERT INTO product (商品編號, 名稱, 單價, 庫存, 分類) VALUES (?, ?, ?, ?, ?)",
                     (product_id, name, price, stock, category))
        conn.commit()
        flash(f"商品 [{name}] 已成功上架！", "success")
    except sqlite3.IntegrityError:
        flash(f"建立失敗：商品編號 [{product_id}] 已重複！", "error")
    finally:
        conn.close()

    return redirect(url_for("list_products"))

@app.route("/product/edit/<product_id>", methods=["POST"])
@login_required
def edit_product(product_id):
    name = request.form.get("name", "").strip()
    price = float(request.form.get("price", 0))
    stock = int(request.form.get("stock", 0))
    category = request.form.get("category", "").strip()

    if price < 0 or stock < 0:
        flash("單價或庫存不可為負數！", "error")
        return redirect(url_for("list_products"))

    conn = get_db()
    conn.execute("UPDATE product SET 名稱 = ?, 單價 = ?, 庫存 = ?, 分類 = ? WHERE 商品編號 = ?",
                 (name, price, stock, category, product_id))
    conn.commit()
    conn.close()
    flash(f"商品 [{name}] 已更新（注意：歷史訂單已保存當初下單價格，不受本次改價影響）！", "success")
    return redirect(url_for("list_products"))

@app.route("/product/delete/<product_id>", methods=["POST"])
@login_required
def delete_product(product_id):
    conn = get_db()
    try:
        conn.execute("DELETE FROM product WHERE 商品編號 = ?", (product_id,))
        conn.commit()
        flash("商品已成功下架刪除！", "info")
    except sqlite3.IntegrityError:
        flash("無法刪除：該商品已存在於歷史訂單明細中，不可刪除！", "error")
    finally:
        conn.close()
    return redirect(url_for("list_products"))

# ==================== 訂單管理 ====================
@app.route("/orders")
@login_required
def list_orders():
    conn = get_db()
    orders = conn.execute("""
        SELECT o.訂單編號, o.客戶編號, o.訂單日期, o.狀態, o.業務人員,
               c.名稱 AS 客戶名稱, c.電話,
               COALESCE(SUM(oi.數量 * oi.單價), 0) AS 總金額
        FROM orders o
        JOIN customer c ON o.客戶編號 = c.客戶編號
        LEFT JOIN order_item oi ON o.訂單編號 = oi.訂單編號
        GROUP BY o.訂單編號
        ORDER BY o.訂單日期 DESC, o.訂單編號 DESC;
    """).fetchall()
    conn.close()
    return render_template("orders.html", orders=orders)

@app.route("/orders/update_status/<order_id>", methods=["POST"])
@login_required
def update_order_status(order_id):
    new_status = request.form.get("status")
    if new_status not in ["處理中", "已出貨", "已完成", "已取消"]:
        flash("無效的訂單狀態！", "error")
        return redirect(url_for("list_orders"))

    conn = get_db()
    conn.execute("UPDATE orders SET 狀態 = ? WHERE 訂單編號 = ?", (new_status, order_id))
    conn.commit()
    conn.close()
    flash(f"訂單 [{order_id}] 狀態已更新為：{new_status}", "success")
    return redirect(url_for("list_orders"))

@app.route("/orders/new", methods=["GET", "POST"])
@login_required
def new_order():
    conn = get_db()
    if request.method == "POST":
        order_id = request.form.get("order_id", "").strip().upper()
        customer_id = request.form.get("customer_id")
        order_date = request.form.get("order_date")
        status = request.form.get("status", "處理中")
        salesperson = request.form.get("salesperson", "").strip()
        selected_products = request.form.getlist("selected_products")

        if not order_id or not customer_id or not selected_products:
            flash("請填寫完整訂單資料，並至少勾選一項商品！", "error")
            conn.close()
            return redirect(url_for("new_order"))

        try:
            # 1. 建立 orders 主表記錄
            conn.execute("""
                INSERT INTO orders (訂單編號, 客戶編號, 訂單日期, 狀態, 業務人員)
                VALUES (?, ?, ?, ?, ?)
            """, (order_id, customer_id, order_date, status, salesperson))

            # 2. 寫入 order_item 明細 (鎖定「當前售價」為下單當時單價，並扣除庫存)
            for prod_id in selected_products:
                qty_raw = request.form.get(f"qty_{prod_id}", "1")
                qty = int(qty_raw) if qty_raw.isdigit() and int(qty_raw) > 0 else 1

                # 讀取該商品目前真實定價 (保存至 order_item 作為歷史憑據)
                prod = conn.execute("SELECT 單價, 庫存 FROM product WHERE 商品編號 = ?", (prod_id,)).fetchone()
                if not prod:
                    continue

                unit_price = prod["單價"]

                conn.execute("""
                    INSERT INTO order_item (訂單編號, 商品編號, 數量, 單價)
                    VALUES (?, ?, ?, ?)
                """, (order_id, prod_id, qty, unit_price))

                # 扣減庫存 (若庫存足夠)
                new_stock = max(0, prod["庫存"] - qty)
                conn.execute("UPDATE product SET 庫存 = ? WHERE 商品編號 = ?", (new_stock, prod_id))

            conn.commit()
            flash(f"訂單 [{order_id}] 建立成功！已鎖定下單單價並更新庫存。", "success")
            conn.close()
            # 直接導向專屬出貨單頁面
            return redirect(url_for("order_detail", order_id=order_id))

        except sqlite3.IntegrityError as e:
            conn.rollback()
            flash(f"建立訂單失敗：訂單編號可能重複或輸入不合規範 ({e})", "error")
            conn.close()
            return redirect(url_for("new_order"))

    # GET 請求：準備下拉選單與商品列表
    customers = conn.execute("SELECT * FROM customer ORDER BY 客戶編號").fetchall()
    products = conn.execute("SELECT * FROM product ORDER BY 商品編號").fetchall()
    conn.close()

    # 自動建議新訂單編號
    today_str = datetime.date.today().strftime("%Y%m%d")
    suggested_order_id = f"ORD-{today_str}-{datetime.datetime.now().strftime('%H%M%S')[-3:]}"
    today = datetime.date.today().strftime("%Y-%m-%d")

    return render_template("order_new.html", 
                           customers=customers, 
                           products=products, 
                           suggested_order_id=suggested_order_id,
                           today=today)

@app.route("/orders/delete/<order_id>", methods=["POST"])
@login_required
def delete_order(order_id):
    conn = get_db()
    conn.execute("DELETE FROM orders WHERE 訂單編號 = ?", (order_id,))
    conn.commit()
    conn.close()
    flash(f"訂單 [{order_id}] 及其明細已刪除！", "info")
    return redirect(url_for("list_orders"))

# ==================== 專屬訂單頁面與出貨單 QRCode ====================
@app.route("/order/<order_id>")
def order_detail(order_id):
    conn = get_db()
    # 查詢訂單與客戶詳細資訊
    order = conn.execute("""
        SELECT o.訂單編號, o.客戶編號, o.訂單日期, o.狀態, o.業務人員,
               c.名稱 AS 客戶名稱, c.電話, c.地址
        FROM orders o
        JOIN customer c ON o.客戶編號 = c.客戶編號
        WHERE o.訂單編號 = ?;
    """, (order_id,)).fetchone()

    if not order:
        conn.close()
        abort(404, description="找不到此訂單資料")

    # 查詢訂單明細 (取出儲存的下單歷史單價)
    items = conn.execute("""
        SELECT oi.商品編號, oi.數量, oi.單價,
               p.名稱 AS 商品名稱, p.分類
        FROM order_item oi
        JOIN product p ON oi.商品編號 = p.商品編號
        WHERE oi.訂單編號 = ?
        ORDER BY oi.商品編號;
    """, (order_id,)).fetchall()
    conn.close()

    total_qty = sum(item["數量"] for item in items)
    grand_total = sum(item["數量"] * item["單價"] for item in items)

    # 產生出貨單專屬 QRCode (編碼本頁完整網址)
    order_url = request.host_url.rstrip("/") + url_for("order_detail", order_id=order_id)
    qr_code_data = generate_qr_code(order_url)

    return render_template("order_detail.html",
                           order=order,
                           items=items,
                           total_qty=total_qty,
                           grand_total=grand_total,
                           qr_code_data=qr_code_data,
                           order_url=order_url)

# ==================== 啟動進入點 ====================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
