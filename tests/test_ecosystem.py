import io
import re
import sqlite3
import unittest
from collections import OrderedDict
from pathlib import Path
from unittest.mock import MagicMock, patch
from PIL import Image
from werkzeug.datastructures import MultiDict
import test_store
import payment_gateway
from app import create_app


class EcosystemTests(unittest.TestCase):
    setUp=test_store.StoreTests.setUp
    tearDown=test_store.StoreTests.tearDown
    csrf=test_store.StoreTests.csrf
    post=test_store.StoreTests.post
    owner=test_store.StoreTests.owner
    fetch=test_store.StoreTests.fetch
    order=test_store.StoreTests.order

    def register(self,email='buyer@example.com',name='Customer One'):
        return self.post('/account/register',dict(name=name,email=email,phone='0601234567',password='customer-password-123',confirm='customer-password-123',consent='on'))

    def submit_cart(self,**overrides):
        self.client.get('/checkout')
        with self.client.session_transaction() as session:
            key=session['checkout_key']
        data=dict(checkout_key=key,name='Test Customer',email='test@example.com',phone='0601234567',fulfillment='collection',address='',consent='on')
        data.update(overrides)
        return self.post('/checkout',data)

    def create_agent(self,code='AGENT01',rate='10'):
        response=self.post('/owner/agents',dict(name='Approved Agent',email='agent@example.com',code=code,rate=rate,approved='on'))
        match=re.search(rb'/agent/activate/([A-Za-z0-9_-]+)',response.data)
        self.assertIsNotNone(match,response.get_data(as_text=True)[:1000])
        return match.group(1).decode()

    def configure_payment(self):
        self.app.config.update(PAYFAST_ENABLED='1',PAYFAST_MODE='sandbox',PAYFAST_MERCHANT_ID='merchant-test',PAYFAST_MERCHANT_KEY='key-test',PAYFAST_PASSPHRASE='private-test-passphrase',PUBLIC_BASE_URL='https://shop.example.com',PAYFAST_ALLOWED_IPS='127.0.0.1/32',PAYFAST_TEST_VALIDATOR=lambda body,mode:True)

    def payment_payload(self,order_id=1,amount=None,reference='PF_TEST_1',status='COMPLETE'):
        token=self.fetch('SELECT token FROM orders WHERE id=?',(order_id,))[0][0]
        response=self.post('/pay/'+token)
        self.assertEqual(response.status_code,200)
        attempt_id,total=self.fetch('SELECT id,amount FROM payment_attempts WHERE order_id=?',(order_id,))[0]
        data=OrderedDict(merchant_id='merchant-test',m_payment_id=attempt_id,pf_payment_id=reference,payment_status=status,amount_gross=f'{total/100:.2f}' if amount is None else amount,custom_str1='')
        data['signature']=payment_gateway.signature(list(data.items()),'private-test-passphrase')
        return data

    def test_shop_navigation_opens_full_catalogue(self):
        response=self.client.get('/')
        self.assertIn(b'href="/shop">Shop</a>',response.data)
        self.assertNotIn(b'href="/#shop">Shop</a>',response.data)
        response=self.client.get('/shop')
        self.assertIn(b'Herbal Combo Pack',response.data)
        self.assertEqual(response.data.count(b'class="product-card"'),6)
        self.assertIn(b'All Products',response.data)
        self.assertIn(b'No reviews yet',response.data)
        for url in ['/track','/account/login','/account/register','/agent/login','/product/1','/contact']:
            self.assertEqual(self.client.get(url).status_code,200,url)

    def test_email_validation_rejects_multiple_recipient_injection(self):
        response=self.order(email='one,two@example.com')
        self.assertIn(b'Enter a valid email address',response.data)
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM orders')[0][0],0)
        self.order()
        self.owner()
        self.app.config.update(PUBLIC_BASE_URL='https://shop.example.com',SMTP_HOST='smtp.example.invalid',SMTP_FROM='orders@example.com')
        with sqlite3.connect(self.db_path) as connection:
            connection.execute("UPDATE notifications SET recipient='one,two@example.com'")
        with patch('ecosystem.smtplib.SMTP') as smtp:
            self.post('/owner/notifications/1/send')
            smtp.assert_not_called()

    def test_customer_history_is_linked_by_customer_id_not_matching_email(self):
        self.order(email='buyer@example.com')
        self.register()
        self.assertNotIn(b'ISZ-00001',self.client.get('/account').data)
        self.order(email='buyer@example.com')
        self.assertIn(b'ISZ-00002',self.client.get('/account').data)
        with self.client.session_transaction() as session:
            buyer=session['customer_id']
        self.post('/account/logout');self.register('other@example.com','Customer Two')
        response=self.client.get('/account')
        self.assertNotIn(b'ISZ-00002',response.data)
        self.assertEqual(self.fetch('SELECT customer_id FROM order_extra WHERE order_id=2')[0][0],buyer)
        self.assertEqual(self.client.get('/owner').status_code,302)
        self.assertEqual(self.client.get('/agent').status_code,302)

    def test_guest_order_claim_requires_receipt_token_and_matching_account(self):
        self.order(email='buyer@example.com')
        token=self.fetch('SELECT token FROM orders')[0][0]
        self.register('wrong@example.com')
        self.post('/account/orders/claim',{'token':token})
        self.assertIsNone(self.fetch('SELECT customer_id FROM order_extra')[0][0])
        self.post('/account/logout');self.register()
        self.post('/account/orders/claim',{'token':token})
        self.assertIsNotNone(self.fetch('SELECT customer_id FROM order_extra')[0][0])
        self.assertIn(b'ISZ-00001',self.client.get('/account').data)

    def test_addresses_saved_items_and_password_change_are_private(self):
        self.register()
        self.post('/account/address',{'label':'Home','address':'123 Example Street, Randburg'})
        address_id=self.fetch('SELECT id FROM customer_addresses')[0][0]
        self.post('/account/saved/1')
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM saved_products')[0][0],1)
        self.post('/account/password',dict(current_password='wrong',password='new-customer-password-123',confirm='new-customer-password-123'))
        self.assertEqual(self.fetch('SELECT auth_version FROM customers')[0][0],0)
        self.post('/account/password',dict(current_password='customer-password-123',password='new-customer-password-123',confirm='new-customer-password-123'))
        self.assertEqual(self.fetch('SELECT auth_version FROM customers')[0][0],1)
        self.post('/account/logout');self.register('other@example.com','Customer Two')
        self.post(f'/account/address/{address_id}/remove')
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM customer_addresses')[0][0],1)
        self.assertNotIn(b'123 Example Street',self.client.get('/account').data)
        self.assertEqual(self.post('/account/login',dict(email='buyer@example.com',password='new-customer-password-123')).status_code,200)

    def test_customer_login_preserves_cart_and_referral(self):
        self.register();self.post('/account/logout')
        self.post('/cart/add/1',{'quantity':'2'})
        self.post('/account/login',dict(email='buyer@example.com',password='customer-password-123'))
        with self.client.session_transaction() as session:
            self.assertEqual(session['cart']['1'],2)
        self.assertIn(b'R400.00',self.client.get('/cart').data)

    def test_track_requires_reference_email_and_phone_digits(self):
        self.order()
        self.assertIn(b'could not match',self.post('/track',dict(reference='ISZ-00001',email='test@example.com',phone_last4='9999')).data)
        response=self.post('/track',dict(reference='ISZ-00001',email='test@example.com',phone_last4='4567'))
        self.assertIn(b'ORDER RECEIVED',response.data)
        self.assertEqual(self.client.get('/order/1').status_code,404)

    def test_promotion_total_shipping_and_atomic_use_limit(self):
        self.owner();self.post('/owner/promotions',dict(code='SAVE20',kind='percent',value='20',minimum='0',max_uses='1',expires='',active='on'));self.post('/owner/logout')
        self.post('/cart/add/2');self.post('/cart/coupon',{'code':'SAVE20'})
        response=self.submit_cart(fulfillment='randburg',address='123 Example Street, Randburg')
        self.assertIn(b'ORDER RECEIVED',response.data)
        self.assertEqual(self.fetch('SELECT subtotal,shipping,total FROM orders')[0],(35000,5000,33000))
        self.assertEqual(self.fetch('SELECT discount FROM order_extra')[0][0],7000)
        self.post('/cart/add/2')
        with self.client.session_transaction() as session:
            session['coupon']='SAVE20'
        response=self.submit_cart()
        self.assertIn(b'usage limit',response.data)
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM orders')[0][0],1)
        self.assertEqual(self.fetch('SELECT stock FROM products WHERE id=2')[0][0],19)
        self.owner();self.post('/owner/order/1',{'status':'Cancelled'});self.post('/owner/logout')
        self.assertIn(b'Promotion applied',self.post('/cart/coupon',{'code':'SAVE20'}).data)

    def test_agent_invite_is_one_use_and_owner_access_is_separate(self):
        self.owner();token=self.create_agent();self.post('/owner/logout')
        self.assertEqual(self.client.get('/agent').status_code,302)
        self.post('/agent/activate/'+token,dict(password='agent-password-long-123',confirm='agent-password-long-123'))
        self.assertEqual(self.client.get('/agent/activate/'+token).status_code,404)
        response=self.post('/agent/login',dict(code='AGENT01',password='agent-password-long-123'))
        self.assertIn(b'SALES AGENT PORTAL',response.data)
        for path in ['/owner','/owner/customers','/owner/reports','/owner/notifications','/owner/agents','/owner/commissions']:
            self.assertEqual(self.client.get(path).status_code,302,path)
        self.assertNotIn(b'password_hash',response.data)
        self.owner();self.post('/owner/agents/1',dict(rate='10'))
        self.post('/owner/logout')
        self.assertNotIn(b'SALES AGENT PORTAL',self.post('/agent/login',dict(code='AGENT01',password='agent-password-long-123')).data)

    def test_commission_snapshot_refund_payout_and_cancellation(self):
        self.owner();self.create_agent();self.post('/owner/logout');self.client.get('/r/AGENT01')
        self.order(quantity=2)
        self.assertEqual(self.fetch('SELECT agent_code,rate_bps FROM order_extra')[0],('AGENT01',1000))
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM commission_ledger')[0][0],0)
        self.owner();self.post('/owner/agents/1',dict(rate='20',approved='on'));self.post('/owner/order/1',{'status':'Paid'})
        self.assertEqual(self.fetch('SELECT target FROM commission_snapshots')[0][0],4000)
        self.post('/owner/order/1',{'status':'Paid'})
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM payments_received')[0][0],1)
        self.client.get('/owner/commissions')
        with self.client.session_transaction() as session:
            key=session['payout_key']
        self.post('/owner/commissions',dict(agent_id='1',amount='20',reference='BANK-PAYOUT-1',event_key=key))
        self.post('/owner/commissions',dict(agent_id='1',amount='20',reference='BANK-PAYOUT-1',event_key=key))
        self.assertEqual(self.fetch("SELECT COUNT(*) FROM commission_ledger WHERE kind='Payout'")[0][0],1)
        self.client.get('/owner/order/1')
        with self.client.session_transaction() as session:
            key=session['refund_key_1']
        self.post('/owner/order/1/refund',dict(goods='100',shipping='0',extra='0',reference='BANK-REFUND-1',reason='Completed test refund',refund_key=key))
        self.assertEqual(self.fetch('SELECT target FROM commission_snapshots')[0][0],3000)
        self.assertEqual(self.fetch('SELECT SUM(amount) FROM commission_ledger')[0][0],1000)
        self.post('/owner/order/1',{'status':'Cancelled'})
        self.assertEqual(self.fetch('SELECT target FROM commission_snapshots')[0][0],0)
        self.assertEqual(self.fetch('SELECT SUM(amount) FROM commission_ledger')[0][0],-2000)
        self.assertEqual(self.fetch('SELECT stock FROM products WHERE id=1')[0][0],20)
        self.assertEqual(self.client.get('/owner/reports?format=csv').status_code,200)

    def test_refund_overcapture_and_duplicate_are_rejected(self):
        self.order();self.owner();self.post('/owner/order/1',{'status':'Paid'});self.client.get('/owner/order/1')
        with self.client.session_transaction() as session:
            key=session['refund_key_1']
        self.post('/owner/order/1/refund',dict(goods='250',shipping='0',extra='0',reference='BANK-R-1',reason='Refund test',refund_key=key))
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM refunds')[0][0],0)
        self.post('/owner/order/1/refund',dict(goods='50',shipping='0',extra='0',reference='BANK-R-1',reason='Refund test',refund_key=key))
        self.post('/owner/order/1/refund',dict(goods='50',shipping='0',extra='0',reference='BANK-R-1',reason='Refund test',refund_key=key))
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM refunds')[0][0],1)

    def test_delivery_updates_customer_tracking_and_drafts_email(self):
        self.order();token=self.fetch('SELECT token FROM orders')[0][0]
        self.owner();self.post('/owner/order/1/delivery',dict(delivery_status='In transit',courier='Demo Courier',tracking_reference='TRACK123',tracking_url='https://courier.example.com/track/TRACK123'))
        response=self.client.get('/order/'+token)
        self.assertIn(b'In transit',response.data);self.assertIn(b'TRACK123',response.data)
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM notifications')[0][0],2)
        self.post('/owner/order/1/delivery',dict(delivery_status='Delivered',tracking_url='javascript:alert(1)'))
        self.assertEqual(self.fetch('SELECT delivery_status FROM order_extra')[0][0],'In transit')

    def test_notifications_are_explicit_sends_and_idempotent_after_success(self):
        self.order();self.owner()
        self.post('/owner/notifications/1/send')
        self.assertEqual(self.fetch('SELECT status FROM notifications WHERE id=1')[0][0],'Queued')
        self.app.config.update(PUBLIC_BASE_URL='https://shop.example.com',SMTP_HOST='smtp.example.invalid',SMTP_FROM='orders@example.com',SMTP_SECURITY='starttls')
        fake=MagicMock()
        with patch('ecosystem.smtplib.SMTP') as smtp:
            smtp.return_value=fake
            fake.__enter__.return_value=fake
            self.post('/owner/notifications/1/send');self.post('/owner/notifications/1/send')
            self.assertEqual(fake.send_message.call_count,1)
            fake.starttls.assert_called_once()
        self.assertEqual(self.fetch('SELECT status FROM notifications WHERE id=1')[0][0],'Sent')

    def test_gateway_disabled_by_default_and_returns_do_not_mark_paid(self):
        self.order();token=self.fetch('SELECT token FROM orders')[0][0]
        response=self.post('/pay/'+token)
        self.assertIn(b'not available',response.data)
        self.client.get('/order/'+token+'?payment=return')
        self.assertEqual(self.fetch('SELECT status FROM orders')[0][0],'Awaiting confirmation')
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM payments_received')[0][0],0)

    def test_gateway_signed_verified_payment_is_idempotent_and_survives_restart(self):
        self.order(quantity=2);self.configure_payment();data=self.payment_payload()
        self.assertEqual(self.client.post('/payments/payfast/itn',data=data).status_code,200)
        self.assertEqual(self.client.post('/payments/payfast/itn',data=data).status_code,200)
        self.assertEqual(self.fetch('SELECT status FROM orders')[0][0],'Paid')
        self.assertEqual(self.fetch('SELECT COUNT(*),SUM(amount) FROM payments_received')[0],(1,40000))
        create_app({'TESTING':True,'DATABASE':self.db_path,'UPLOAD_DIR':str(Path(self.tmp.name)/'uploads')})
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM payments_received')[0][0],1)

    def test_gateway_rejects_signature_amount_ip_and_failed_server_confirmation(self):
        self.order();self.configure_payment();data=self.payment_payload()
        bad=dict(data);bad['signature']='bad'
        self.assertEqual(self.client.post('/payments/payfast/itn',data=bad).status_code,400)
        bad=dict(data);bad['amount_gross']='1.00';bad['signature']=payment_gateway.signature(list(bad.items()),'private-test-passphrase')
        self.assertEqual(self.client.post('/payments/payfast/itn',data=bad).status_code,400)
        self.app.config['PAYFAST_ALLOWED_IPS']='197.97.145.144/28'
        self.assertEqual(self.client.post('/payments/payfast/itn',data=data,headers={'X-Forwarded-For':'197.97.145.145'}).status_code,400)
        self.app.config['PAYFAST_ALLOWED_IPS']='127.0.0.1/32';self.app.config['PAYFAST_TEST_VALIDATOR']=lambda body,mode:False
        self.assertEqual(self.client.post('/payments/payfast/itn',data=data).status_code,503)
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM payments_received')[0][0],0)
        self.assertEqual(self.fetch('SELECT status FROM orders')[0][0],'Awaiting confirmation')
        duplicated=MultiDict(list(data.items())+[('merchant_id','merchant-test')])
        self.assertEqual(self.client.post('/payments/payfast/itn',data=duplicated).status_code,400)

    def test_gateway_late_payment_after_cancellation_never_reopens_order(self):
        self.order();self.configure_payment();data=self.payment_payload();self.owner();self.post('/owner/order/1',{'status':'Cancelled'})
        self.assertEqual(self.client.post('/payments/payfast/itn',data=data).status_code,200)
        self.assertEqual(self.fetch('SELECT status FROM orders')[0][0],'Cancelled')
        self.assertEqual(self.fetch('SELECT stock FROM products WHERE id=1')[0][0],20)
        self.assertEqual(self.fetch('SELECT SUM(amount) FROM payments_received')[0][0],20000)

    def test_review_requires_purchase_and_publication(self):
        self.register();self.post('/product/1/review',dict(rating='5',comment='A helpful product experience.'))
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM product_reviews')[0][0],0)
        self.order();self.owner();self.post('/owner/order/1',{'status':'Paid'});self.post('/owner/logout')
        self.post('/account/login',dict(email='buyer@example.com',password='customer-password-123'))
        self.post('/product/1/review',dict(rating='5',comment='A helpful product experience.'))
        self.assertEqual(self.fetch('SELECT status FROM product_reviews')[0][0],'Pending')
        self.assertNotIn(b'A helpful product experience.',self.client.get('/product/1').data)
        self.owner();self.post('/owner/reviews',dict(review_id='1',status='Published'))
        self.assertIn(b'A helpful product experience.',self.client.get('/product/1').data)
        self.assertIn(b'5.0',self.client.get('/shop').data)

    def test_owner_operations_and_product_details_gallery(self):
        self.owner()
        for url in ['/owner/agents','/owner/commissions','/owner/customers','/owner/reports','/owner/promotions','/owner/reviews','/owner/notifications','/owner/integrations']:
            self.assertEqual(self.client.get(url).status_code,200,url)
        self.post('/owner/product/1/details',dict(benefits='Owner-confirmed information.',ingredients='Verified ingredient list.',directions='Follow the confirmed label.'))
        self.assertIn(b'Verified ingredient list.',self.client.get('/product/1').data)
        picture=io.BytesIO();Image.new('RGB',(100,70),'green').save(picture,'PNG');picture.seek(0)
        self.post('/owner/product/1/gallery',{'images':(picture,'detail.png')})
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM product_gallery')[0][0],1)
        self.assertIn(b'data-product-image',self.client.get('/product/1').data)
        self.post('/owner/product/1/gallery/1/remove')
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM product_gallery')[0][0],0)


class GatewayHelperTests(unittest.TestCase):
    def test_php_url_encoding_and_signature_empty_fields(self):
        self.assertEqual(payment_gateway.encode('A ~ B'), 'A+%7E+B')
        pairs=[('first','A B'),('blank','')]
        self.assertEqual(payment_gateway.parameter_string(pairs),'first=A+B&blank=')
        self.assertNotEqual(payment_gateway.signature(pairs,'test'),payment_gateway.signature(pairs,'test',outgoing=True))

    def test_server_validation_never_follows_redirects_and_fails_closed(self):
        with patch('payment_gateway.urllib.request.build_opener') as opener:
            opener.return_value.open.side_effect=OSError('offline')
            self.assertFalse(payment_gateway.server_validates('amount=1.00','sandbox'))
        self.assertIsNone(payment_gateway.NoRedirect().redirect_request(None,None,None,None,None,None))
