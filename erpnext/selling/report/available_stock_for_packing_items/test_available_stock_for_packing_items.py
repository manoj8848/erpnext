import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.accounts.doctype.payment_entry.test_payment_entry import make_test_item
from erpnext.selling.doctype.product_bundle.test_product_bundle import make_product_bundle

class TestAvailableStockForPackingItems(FrappeTestCase):
	def setUp(self):
		self.item = make_test_item("_Test Product Bundle")
		item_1 = make_test_item("_Test Bundle Item 1")
		item_2 = make_test_item("_Test Bundle Item 2")
		make_product_bundle(self.item.item_code, [item_1.item_code, item_2.item_code])

	def tearDown(self):
		frappe.db.rollback()

	def test_available_stock_for_packing_codecov(self):
		from .available_stock_for_packing_items import execute
		data = execute()
		if data[1]:
			for row in data[1]:
				if row[0] == self.item.item_code:
					self.assertEqual(row[0], "_Test Product Bundle")
					self.assertEqual(row[3], "Nos")
					self.assertEqual(row[4], "_Test Warehouse - _TC")
