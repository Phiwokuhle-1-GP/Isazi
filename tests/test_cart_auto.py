"""Server-authoritative cart responses used by automatic quantity updates."""
import unittest
import test_store


class CartAutoTests(unittest.TestCase):
    setUp=test_store.StoreTests.setUp
    tearDown=test_store.StoreTests.tearDown
    csrf=test_store.StoreTests.csrf
    post=test_store.StoreTests.post
    owner=test_store.StoreTests.owner
    fetch=test_store.StoreTests.fetch
    def test_auto_cart_updates_totals_badge_and_last_item_removal(self):
        self.post('/cart/add/1', {'quantity':'1'})
        page=self.client.get('/cart').data
        self.assertIn(b'cart-auto.js',page)
        self.assertIn(b'data-cart-auto-update',page)
        self.assertIn(b'data-cart-manual-update',page)
        # Same POST + redirect-follow request performed by cart-auto.js.
        response=self.post('/cart/update/1',{'quantity':'3'})
        self.assertIn(b'Your cart, 3 items',response.data)
        self.assertIn(b'R600.00',response.data)
        self.assertIn(b'value="3"',response.data)
        self.post('/cart/update/1',{'quantity':'2'})
        response=self.post('/cart/remove/1')
        self.assertIn(b'Your cart is empty',response.data)
        self.assertIn(b'Your cart, 0 items',response.data)
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM orders')[0][0],0)

    def test_zero_removes_item_and_failed_stock_change_keeps_server_quantity(self):
        self.post('/cart/add/1',{'quantity':'2'})
        response=self.post('/cart/update/1',{'quantity':'99'})
        self.assertIn(b'The requested quantity is not available',response.data)
        self.assertIn(b'value="2"',response.data)
        response=self.post('/cart/update/1',{'quantity':'0'})
        self.assertIn(b'Your cart is empty',response.data)
        with self.client.session_transaction() as session:
            self.assertEqual(session.get('cart'),{})

    def test_quantity_update_recalculates_coupon_and_keeps_csrf_required(self):
        self.owner()
        self.post('/owner/promotions',dict(code='CART10',kind='percent',value='10',minimum='0',max_uses='10',expires='',active='on'))
        self.post('/owner/logout')
        self.post('/cart/add/1',{'quantity':'1'})
        self.post('/cart/coupon',{'code':'CART10'})
        response=self.post('/cart/update/1',{'quantity':'3'})
        self.assertIn(b'R600.00',response.data)
        self.assertIn(b'R540.00',response.data)
        self.assertEqual(self.client.post('/cart/remove/1').status_code,400)
        with self.client.session_transaction() as session:
            self.assertEqual(session['cart'],{'1':3})

    def test_auto_script_only_loads_on_cart(self):
        for route in ('/','/shop','/product/1'):
            self.assertNotIn(b'cart-auto.js',self.client.get(route).data)

