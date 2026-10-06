import unittest
from app import app, get_db

class OrderManagementSystemTests(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_login_page_renders(self):
        """測試未登入時進入首頁會被導向至登入頁面"""
        response = self.app.get('/', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('管理員登入'.encode('utf-8'), response.data)

    def test_admin_login_success(self):
        """測試管理員帳號 admin / admin123 登入成功並進入儀表板"""
        response = self.app.post('/login', data={
            'username': 'admin',
            'password': 'admin123'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('系統總覽儀表板'.encode('utf-8'), response.data)

    def test_order_detail_and_shipping_note(self):
        """測試專屬訂單頁面 /order/<訂單編號> 正確顯示出貨單與 QRCode"""
        response = self.app.get('/order/ORD-20260301')
        self.assertEqual(response.status_code, 200)
        self.assertIn('智慧倉儲出貨單'.encode('utf-8'), response.data)
        self.assertIn('ORD-20260301'.encode('utf-8'), response.data)
        self.assertIn('data:image/png;base64,'.encode('utf-8'), response.data)

    def test_order_status_update(self):
        """測試訂單狀態直接更新功能"""
        # 先登入
        self.app.post('/login', data={'username': 'admin', 'password': 'admin123'})
        # 更新狀態為 已出貨
        response = self.app.post('/orders/update_status/ORD-20260303', data={'status': '已出貨'}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        # 驗證資料庫狀態確實變更
        conn = get_db()
        order = conn.execute("SELECT 狀態 FROM orders WHERE 訂單編號 = 'ORD-20260303'").fetchone()
        conn.close()
        self.assertEqual(order['狀態'], '已出貨')

if __name__ == '__main__':
    unittest.main()
