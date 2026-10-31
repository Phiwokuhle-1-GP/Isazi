"""Dashboard read-only scopes and totals use real persisted records."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from app import create_app

class OwnerWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=str(Path(self.temp.name)/'shop.sqlite3')
        self.app=create_app({'TESTING':True,'DATABASE':self.path,'UPLOAD_DIR':str(Path(self.temp.name)/'uploads')})
        self.app.secret_key='test-only-secret'
        self.client=self.app.test_client()
        with self.client.session_transaction() as session: session['admin']=True
        with sqlite3.connect(self.path) as db:
            for i,name,status,test,delivery in [(1,'Real paid','Paid',0,'Payment confirmed'),(2,'Test paid','Paid',1,'Not arranged'),(3,'Real pending','Awaiting confirmation',0,'Not arranged'),(4,'Already sent','Paid',0,'In transit')]:
                db.execute("INSERT INTO orders(id,token,checkout_key,name,email,phone,fulfillment,address,notes,subtotal,shipping,total,status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(i,str(i),str(i),name,'example@example.com','0600000000','collection','','',10000,0,10000,status))
                db.execute('INSERT INTO order_extra(order_id,payment_test,delivery_status) VALUES(?,?,?)',(i,test,delivery))
            for i,amount in [(1,10000),(2,990000),(4,10000)]:
                db.execute('INSERT INTO payments_received(order_id,event_key,amount,method,reference) VALUES(?,?,?,?,?)',(i,str(i),amount,'test fixture','fixture'))
    def tearDown(self): self.temp.cleanup()
    def test_metrics_exclude_test_receipts_and_dispatched_orders(self):
        with self.app.test_request_context('/owner'):
            from flask import session, template_rendered
            session['admin']=True
            captured=[]
            def record(sender,template,context,**extra): captured.append(context)
            template_rendered.connect(record,self.app)
            try:self.app.view_functions['owner']()
            finally:template_rendered.disconnect(record,self.app)
            context=captured[0]
            self.assertEqual(context['owner_stats']['received'],20000)
            self.assertEqual(context['owner_stats']['dispatch'],1)
            self.assertEqual(context['trend_total'],20000)
            self.assertEqual(context['counts']['orders'],3)
    def test_filters_and_owner_access(self):
        text=self.client.get('/owner?view=orders&scope=test').text
        self.assertIn('Test paid',text);self.assertNotIn('Real paid',text)
        text=self.client.get('/owner?view=orders&status=dispatch').text
        self.assertIn('Real paid',text);self.assertNotIn('Already sent',text)
        text=self.client.get('/owner?view=orders&q=ISZ-00003').text
        self.assertIn('Real pending',text);self.assertNotIn('Real paid',text)
        self.assertEqual(self.client.get('/owner?view=unknown').status_code,200)
        with self.client.session_transaction() as session:session.clear()
        self.assertEqual(self.client.get('/owner').status_code,302)
        self.assertNotIn('owner-sidebar',self.client.get('/').text)
    def test_product_filter_uses_real_stock_and_hides_inactive(self):
        with sqlite3.connect(self.path) as db:
            db.execute('UPDATE products SET stock=10')
            db.execute('UPDATE products SET stock=1 WHERE id IN (1,2)')
            db.execute('UPDATE products SET active=0 WHERE id=2')
        text=self.client.get('/owner?view=products&stock=low').text
        self.assertIn('Smolo Body Cured System',text)
        self.assertNotIn('Ukhlanza Isibindi',text)
