import frappe
from frappe.utils import today, add_days
from frappe.tests.utils import FrappeTestCase

from erpnext.accounts.doctype.payment_entry.test_payment_entry import make_test_item
from erpnext.buying.report.purchase_analytics.purchase_analytics import execute

class TestPurchaseAnalytics(FrappeTestCase):
	def setUp(self):
		self.item = make_test_item("test_purchase_item")
		po = self.create_purchase_order()
		po.submit()

		self.filters = frappe._dict(
			company = po.company,
			from_date = add_days(today(), -30),
			to_date = today(),
			tree_type = "Item",
			value_quantity = "Value",
			range = "Monthly",
			doc_type = "Purchase Order"
		)

	def tearDown(self):
		frappe.db.rollback()

	def test_purchase_analytics_report_codecov(self):
		data = execute(self.filters)
		for item in data[1]:
			if item.get("entity") == self.item.item_code:
				self.assertEqual(item.get("entity"), "test_purchase_item")
				self.assertEqual(item.get("entity_name"), "_Test Item")
				self.assertEqual(item.get("total"), 5000)

		# based on quantity
		self.filters.update({"value_quantity": "Quantity"})
		data_quantity = execute(self.filters)
		for row in data_quantity[1]:
			if row.get("entity") == self.item.item_code:
				self.assertEqual(row.get("entity"), "test_purchase_item")
				self.assertEqual(row.get("entity_name"), "_Test Item")
				self.assertEqual(row.get("total"), 10)

	def create_purchase_order(self):
		po = frappe.copy_doc(test_records[0]).insert()
		po = frappe.get_doc("Purchase Order", po.name)
		po.transaction_date = today()
		po.schedule_date = today()
		po.items[0].item_code = self.item.item_code
		po.items[0].schedule_date = today()
		po.save()

		return po

test_records = frappe.get_test_records("Purchase Order")