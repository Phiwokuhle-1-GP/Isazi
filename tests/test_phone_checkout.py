import io
import json
import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch
import test_store
from app import create_app
from simple_checkout import normalize_phone

class PhoneCheckoutTests(unittest.TestCase):
    tearDown=test_store.StoreTests.tearDown
    csrf=test_store.StoreTests.csrf
    post=test_store.StoreTests.post
    owner=test_store.StoreTests.owner
    fetch=test_store.StoreTests.fetch

    def setUp(self):
        test_store.StoreTests.setUp(self)
        self.app.config['DEMO_PAYMENTS_ENABLED']=True
        self.branch=json.loads((Path(__file__).parents[1]/'data/paxi_branches.json').read_text())['branches'][0]['code']
        with sqlite3.connect(self.db_path) as db:
            db.execute("INSERT INTO simple_settings VALUES('pep_fee','6000')")
            db.execute("INSERT INTO simple_settings VALUES('shop_url','https://shop.example.com')")

    def register(self,**values):
        data=dict(phone='0601234567',pin='0456',confirm_pin='0456',preference='pep',branch_code=self.branch,consent='on');data.update(values)
        return self.post('/account/register',data)

    def checkout(self,**values):
        self.post('/cart/add/1',{'quantity':1});self.client.get('/checkout')
        with self.client.session_transaction() as s:key=s['checkout_key']
        data=dict(checkout_key=key,name='Test Recipient',fulfillment='pep',branch_code=self.branch,consent='on');data.update(values)
        return self.post('/checkout',data)

    def test_normalization_registration_pin_hash_and_duplicate(self):
        self.assertEqual(normalize_phone('+27 60 123 4567'),'0601234567')
        self.assertEqual(normalize_phone('abc0601234567'),'')
        self.assertEqual(self.register().status_code,200)
        row=self.fetch('SELECT phone,pin_hash FROM phone_accounts')[0]
        self.assertEqual(row[0],'0601234567');self.assertNotEqual(row[1],'0456')
        self.assertIn(b'ISZ-C0000001',self.client.get('/account').data)
        self.assertNotIn(b'@phone.invalid',self.client.get('/account').data)
        self.post('/account/logout');self.assertEqual(self.register(phone='+27601234567').status_code,400)
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM customers')[0][0],1)

    def test_pin_login_lock_is_per_account_across_ips(self):
        self.register();self.post('/account/logout')
        for i in range(5):
            self.client.post('/account/login',data={'csrf_token':self.csrf(),'phone':'0601234567','pin':'9999'},environ_overrides={'REMOTE_ADDR':'10.0.0.'+str(i)})
        response=self.client.post('/account/login',data={'csrf_token':self.csrf(),'phone':'0601234567','pin':'0456'},environ_overrides={'REMOTE_ADDR':'10.0.0.99'})
        self.assertEqual(response.status_code,429)
        self.assertEqual(self.client.get('/account').status_code,302)

    def test_pin_change_immutable_number_and_login(self):
        self.register()
        self.post('/account/details',dict(name='New Name',phone='0712345678'))
        self.assertEqual(self.fetch('SELECT phone FROM customers')[0][0],'0601234567')
        self.post('/account/pin',dict(current_pin='0456',pin='9876',confirm_pin='9876'))
        self.post('/account/logout')
        self.assertEqual(self.post('/account/login',dict(phone='+27601234567',pin='9876')).status_code,200)
        self.assertEqual(self.client.get('/account').status_code,200)

    def test_pep_pending_payment_owner_confirmation_dispatch_idempotence(self):
        self.register();response=self.checkout()
        self.assertIn(b'Pending payment confirmation',response.data)
        self.assertNotIn(b'Choose Demo Payment',response.data)
        self.assertEqual(self.fetch('SELECT shipping,total,status,phone FROM orders')[0],(5995,25995,'Awaiting confirmation','0601234567'))
        token=self.fetch('SELECT token FROM orders')[0][0]
        self.assertEqual(self.post('/demo/order/'+token+'/payment/visa/complete',follow=False).status_code,409)
        self.owner()
        self.post('/owner/order/1',dict(status='Ready'))
        self.assertEqual(self.fetch('SELECT status FROM orders')[0][0],'Awaiting confirmation')
        self.post('/owner/order/1/delivery',dict(delivery_status='In transit',tracking_reference='D12345',courier='PAXI'))
        self.assertEqual(self.fetch('SELECT delivery_status FROM order_extra')[0][0],'Awaiting payment')
        for _ in range(2):self.post('/owner/order/1/confirm-eft',dict(verified='on',bank_reference='BANK-123'))
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM payments_received')[0][0],1)
        for _ in range(2):self.post('/owner/order/1/delivery',dict(delivery_status='In transit',tracking_reference='D12345',courier='PAXI'))
        self.assertEqual(self.fetch('SELECT status FROM orders')[0][0],'Paid')
        self.assertEqual(self.fetch('SELECT status FROM sms_outbox'),[('Test - not sent',)]*3)
        with patch('simple_checkout.urlopen') as send:
            self.assertEqual(self.post('/owner/sms/1/send',follow=False).status_code,409);send.assert_not_called()

    def test_bad_branch_rejected_and_missing_old_fee_uses_fixed_standard_price(self):
        self.register();self.checkout(branch_code='FAKE')
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM orders')[0][0],0)
        with sqlite3.connect(self.db_path) as db:db.execute("DELETE FROM simple_settings WHERE key='pep_fee'")
        self.checkout()
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM orders')[0][0],1)
        self.assertEqual(self.fetch('SELECT shipping FROM orders')[0][0],5995)
        self.assertEqual(self.fetch('SELECT presentation_stock FROM products WHERE id=1')[0][0],48)

    def test_fixed_pep_fee_over_600_and_reference_saved(self):
        self.register();self.post('/cart/add/1',{'quantity':3});self.checkout() # 4 x 200
        self.assertEqual(self.fetch('SELECT shipping,total FROM orders')[0],(5995,85995))
        self.assertEqual(self.fetch('SELECT payment_reference,branch_code FROM pep_orders')[0],('0601234567',self.branch))

    def test_qr_registration_keeps_single_product_and_preserves_cart(self):
        with self.client.session_transaction() as s:s['cart']={'2':2}
        self.app.config['CUSTOMER_CHECKOUT_REQUIRED']=True
        self.assertEqual(self.client.get('/buy/6').location,'/checkout')
        self.assertIn(b'data-payment-choice',self.client.get('/checkout').data)
        self.post('/checkout/payment-choice',{'payment_method':'pep'})
        result=self.register();self.assertIn(b'Choose your PEP store',result.data)
        with self.client.session_transaction() as s:key=s['checkout_key']
        self.post('/checkout',dict(checkout_key=key,name='QR Customer',fulfillment='pep',branch_code=self.branch,consent='on'))
        self.assertEqual(self.fetch('SELECT product_id,quantity FROM order_items'),[(6,1)])
        with self.client.session_transaction() as s:self.assertEqual(s['cart'],{'2':2})
        self.assertEqual(self.client.get('/buy/999999').status_code,404)

    def test_qr_png_uses_configured_url_and_owner_cannot_buy(self):
        response=self.client.get('/product/6/qr.png')
        self.assertEqual(response.status_code,200);self.assertTrue(response.data.startswith(b'\x89PNG'))
        from PIL import Image
        self.assertGreaterEqual(Image.open(io.BytesIO(response.data)).width,300)
        with patch('qrcode.QRCode.add_data') as add:
            self.client.get('/product/6/qr.png');add.assert_called_once_with('https://shop.example.com/buy/6')
        self.owner();self.assertEqual(self.client.get('/buy/6').status_code,403)
        self.assertEqual(self.register().status_code,403)

    def test_bank_snapshot_and_live_sms_configuration_gate(self):
        with sqlite3.connect(self.db_path) as db:
            for k,v in [('capitec_holder','Test Only'),('capitec_number','1234567890'),('capitec_type','Business')]:db.execute('INSERT INTO simple_settings VALUES(?,?)',(k,v))
        self.app.config['DEMO_PAYMENTS_ENABLED']=False
        self.register();page=self.checkout();self.assertIn(b'Test Only',page.data)
        token=self.fetch('SELECT token FROM orders')[0][0]
        self.assertEqual(self.post('/pay/'+token,follow=False).status_code,409)
        with sqlite3.connect(self.db_path) as db:db.execute("UPDATE simple_settings SET value='Changed holder' WHERE key='capitec_holder'")
        self.assertIn(b'Test Only',self.client.get('/order/'+token).data)
        self.owner();self.post('/owner/order/1/confirm-eft',dict(verified='on',bank_reference='BANK-1'))
        self.post('/owner/order/1/delivery',dict(delivery_status='In transit',tracking_reference='D123',courier='PAXI'))
        with patch('simple_checkout.urlopen') as send:
            self.post('/owner/sms/1/send');send.assert_not_called()
        self.assertEqual(self.fetch('SELECT status FROM sms_outbox'),[('Superseded',),('Queued',),('Queued',)])

    def test_live_sms_success_is_once_and_provider_timeout_never_blind_retried(self):
        self.app.config['DEMO_PAYMENTS_ENABLED']=False
        self.register();self.checkout();self.owner()
        self.post('/owner/order/1/confirm-eft',dict(verified='on',bank_reference='BANK-1'))
        self.post('/owner/order/1/delivery',dict(delivery_status='In transit',tracking_reference='D123',courier='PAXI'))
        with sqlite3.connect(self.db_path) as db:
            for key,value in [('sms_enabled','1'),('sms_sid','AC'+'a'*32),('sms_token','b'*32),('sms_from','+27601234567')]:
                db.execute('INSERT INTO simple_settings VALUES(?,?)',(key,value))
        with patch('simple_checkout.urlopen') as send:
            send.return_value.__enter__.return_value=io.BytesIO(json.dumps({'sid':'SM'+'c'*32,'status':'queued'}).encode())
            self.post('/owner/sms/3/send');self.assertEqual(send.call_count,1)
            self.assertEqual(self.post('/owner/sms/3/send',follow=False).status_code,409);self.assertEqual(send.call_count,1)
        self.assertEqual(self.fetch('SELECT status FROM sms_outbox WHERE id=3')[0][0],'Provider accepted')
        with patch('simple_checkout.urlopen',side_effect=TimeoutError) as send:
            self.post('/owner/order/1/delivery',dict(delivery_status='Ready for collection',tracking_reference='D123',courier='PAXI'))
            self.assertEqual(send.call_count,1)
            self.assertEqual(self.post('/owner/sms/4/send',follow=False).status_code,409);self.assertEqual(send.call_count,1)
        self.assertEqual(self.fetch('SELECT status FROM sms_outbox WHERE id=4')[0][0],'Sending - reconcile before retry')

    def test_automatic_notifications_full_live_journey_and_replays(self):
        self.app.config['DEMO_PAYMENTS_ENABLED']=False
        with sqlite3.connect(self.db_path) as db:
            for key,value in [('sms_enabled','1'),('sms_sid','AC'+'a'*32),('sms_token','b'*32),('sms_from','+27601234567')]:
                db.execute('INSERT INTO simple_settings VALUES(?,?)',(key,value))
        self.register()
        with patch('simple_checkout.urlopen') as send:
            send.return_value.__enter__.side_effect=lambda:io.BytesIO(json.dumps({'sid':'SM'+'c'*32}).encode())
            page=self.checkout();self.assertEqual(send.call_count,1)
            self.assertIn(b'Pending payment confirmation',page.data)
            self.owner()
            for _ in range(2):self.post('/owner/order/1/confirm-eft',dict(verified='on',bank_reference='BANK-1'))
            self.assertEqual(send.call_count,2)
            for _ in range(2):self.post('/owner/order/1/delivery',dict(delivery_status='In transit',tracking_reference='D123',courier='PAXI'))
            self.assertEqual(send.call_count,3)
            self.post('/owner/order/1/delivery',dict(delivery_status='Ready for collection',tracking_reference='D123',courier='PAXI'))
            self.assertEqual(send.call_count,4)
        self.assertEqual(self.fetch('SELECT status FROM sms_outbox'),[('Provider accepted',)]*4)
        self.assertIn('payment received and confirmed',self.fetch('SELECT body FROM sms_outbox WHERE id=2')[0][0])
        self.assertIn('PAXI sends your collection PIN when the parcel is ready',self.fetch('SELECT body FROM sms_outbox WHERE id=3')[0][0])

    def test_only_bundle_deals_and_new_marked_bundles_have_qr(self):
        with sqlite3.connect(self.db_path) as db:
            db.execute("INSERT INTO products(name,category,price,stock,image,description,active) VALUES('New special','General Health',12300,5,'','Special',1)")
            db.execute("UPDATE products SET is_bundle=1 WHERE name='New special'")
        products=self.fetch('SELECT id FROM products WHERE active=1 AND is_bundle=1')
        for (pid,) in products:
            with patch('qrcode.QRCode.add_data') as add:
                self.assertEqual(self.client.get(f'/product/{pid}/qr.png').status_code,200)
                add.assert_called_once_with(f'https://shop.example.com/buy/{pid}')
        self.assertIn(b'/product/6/qr.png',self.client.get('/').data)
        self.assertIn(b'Buy Now',self.client.get('/shop').data)
        self.assertNotEqual(self.client.get('/owner/product-qr').status_code,200)
        self.owner();page=self.client.get('/owner/product-qr')
        self.assertEqual(page.status_code,200)
        for (pid,) in products:self.assertIn(f'/product/{pid}/qr.png'.encode(),page.data)
        with sqlite3.connect(self.db_path) as db:db.execute('UPDATE products SET active=0 WHERE id=6')
        self.assertEqual(self.client.get('/product/6/qr.png').status_code,404)

    def test_enabled_sms_never_sends_test_order_events(self):
        with sqlite3.connect(self.db_path) as db:
            for key,value in [('sms_enabled','1'),('sms_sid','AC'+'a'*32),('sms_token','b'*32),('sms_from','+27601234567')]:
                db.execute('INSERT INTO simple_settings VALUES(?,?)',(key,value))
        with patch('simple_checkout.urlopen') as send:
            self.register();self.checkout();self.owner()
            self.post('/owner/order/1/confirm-eft',dict(verified='on',bank_reference='TEST-1'))
            self.post('/owner/order/1/delivery',dict(delivery_status='In transit',tracking_reference='TEST123',courier='PAXI'))
            self.post('/owner/order/1/delivery',dict(delivery_status='Ready for collection',tracking_reference='TEST123',courier='PAXI'))
            send.assert_not_called()
        self.assertEqual(self.fetch('SELECT status FROM sms_outbox'),[('Test - not sent',)]*4)

    def test_rolled_back_checkout_does_not_send_or_store_notifications(self):
        self.register()
        with patch('simple_checkout.urlopen') as send:
            self.checkout(branch_code='INVALID')
            send.assert_not_called()
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM sms_outbox')[0][0],0)

    def test_regular_products_cannot_start_quick_purchase(self):
        self.assertEqual(self.client.get('/buy/1').status_code,404)
        self.assertEqual(self.client.get('/product/1/qr.png').status_code,404)
        self.assertNotIn(b'product-qr',self.client.get('/product/1').data)
        self.assertIn(b'bundle-mobile-buy',self.client.get('/product/6').data)
        self.owner()
        self.post('/owner/product/1',dict(name='New bundle',category='General Health',price='200',stock='5',description='Bundle of herbal products',active='on',is_bundle='on'))
        self.assertEqual(self.fetch('SELECT is_bundle FROM products WHERE id=1')[0][0],1)
        self.assertEqual(self.client.get('/product/1/qr.png').status_code,200)

    def test_account_creation_is_delayed_until_payment_choice(self):
        self.app.config['CUSTOMER_CHECKOUT_REQUIRED']=True
        result=self.post('/cart/add/1',{'quantity':'2'},follow=False)
        self.assertNotEqual(result.location,'/account/register')
        with self.client.session_transaction() as s:self.assertEqual(s['cart'],{'1':2})
        page=self.client.get('/checkout')
        self.assertEqual(page.status_code,200)
        self.assertIn(b'data-payment-choice',page.data)
        self.assertNotIn(b'name="phone"',page.data)
        self.post('/checkout/payment-choice',{'payment_method':'pep'})
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM customers')[0][0],0)
        failed=self.register(confirm_pin='9999')
        self.assertEqual(failed.status_code,400)
        self.assertIn(b'Confirm PIN',failed.data)
        self.assertNotIn(b'name="branch_code"',failed.data)
        result=self.register()
        self.assertIn(b'Choose your PEP store',result.data)
        with self.client.session_transaction() as s:self.assertEqual(s['cart'],{'1':2})
        self.assertEqual(self.fetch('SELECT preference,branch_code FROM phone_accounts')[0],('pep',''))

    def test_payment_checkout_blocks_unregistered_order_post(self):
        self.app.config['CUSTOMER_CHECKOUT_REQUIRED']=True
        self.post('/cart/add/1')
        page=self.post('/checkout',{'name':'Guest','fulfillment':'collection','consent':'on'})
        self.assertIn(b'data-payment-choice',page.data)
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM orders')[0][0],0)
