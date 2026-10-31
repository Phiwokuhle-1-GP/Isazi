import sqlite3
import unittest
import test_store
from app import create_app

class CatalogAdditionsTests(unittest.TestCase):
    setUp=test_store.StoreTests.setUp
    tearDown=test_store.StoreTests.tearDown
    fetch=test_store.StoreTests.fetch

    def restart(self):
        return create_app({'TESTING':True,'DATABASE':self.db_path,'UPLOAD_DIR':self.tmp.name+'/uploads'})

    def test_eight_products_and_prices(self):
        self.assertEqual(self.fetch('SELECT count(*) FROM products')[0][0],8)
        self.assertEqual(self.fetch("SELECT price FROM products WHERE name='Nyawozeni'")[0][0],15000)
        self.assertEqual(self.fetch("SELECT price FROM products WHERE name='Soursop Leaves'")[0][0],12000)
        page=self.client.get('/').get_data(as_text=True)
        section=page.split('id="best-sellers"')[1].split('</section>')[0]
        self.assertEqual(section.count('class="product-card"'),8)
        for name in ['Nyawozeni','Soursop Leaves']:
            self.assertIn(name,self.client.get('/shop').get_data(as_text=True))

    def test_upgrade_is_once_and_keeps_owner_changes(self):
        with sqlite3.connect(self.db_path) as db:
            db.execute("DELETE FROM products WHERE image IN ('nyawozeni.png','soursop-leaves.png')")
            db.execute("DELETE FROM settings WHERE key='catalog_products_2629'")
        self.restart()
        self.assertEqual(self.fetch('SELECT count(*) FROM products')[0][0],8)
        with sqlite3.connect(self.db_path) as db:
            db.execute("UPDATE products SET name='Custom name',price=17500,active=0 WHERE image='nyawozeni.png'")
            db.execute("DELETE FROM products WHERE image='soursop-leaves.png'")
        self.restart()
        self.assertEqual(self.fetch('SELECT count(*) FROM products')[0][0],7)
        self.assertEqual(self.fetch("SELECT name,price,active FROM products WHERE image='nyawozeni.png'")[0],('Custom name',17500,0))
