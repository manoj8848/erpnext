import frappe
from frappe.utils import today, add_days
from frappe.tests.utils import FrappeTestCase

from erpnext.accounts.doctype.payment_entry.test_payment_entry import make_test_item
from erpnext.buying.report.item_wise_purchase_history.item_wise_purchase_history import execute

class TestItemWisePurchaseHistory(FrappeTestCase):
	def setUp(self):
		self.item = make_test_item("test_report_item")
		po = self.create_purchase_order()
		po.submit()

		self.filters = frappe._dict(
			company = po.company,
			from_date = add_days(today(), -30),
			to_date = today(),
			item_code = self.item.item_name
		)

	def tearDown(self):
		frappe.db.rollback()

	def test_item_wise_purchase_history_TC_B_214(self):
		data = execute(self.filters)
		report_data = data[1][0]
		if report_data.get("item_code") == self.item.item_code:
			self.assertEqual(report_data.get("item_code"), "test_report_item")
			self.assertEqual(report_data.get("item_group"), "Products")
			self.assertEqual(report_data.get("quantity"), 10)
			self.assertEqual(report_data.get("uom"), "_Test UOM")
			self.assertEqual(report_data.get("rate"), 500)
			self.assertEqual(report_data.get("amount"), 5000)
			self.assertEqual(report_data.get("supplier"), "_Test Supplier")
			self.assertEqual(report_data.get("company"), "_Test Company")

	def test_validate_filters_TC_B_215(self):
		self.filters.update({"from_date": today(),"to_date": add_days(today(), -1)})

		with self.assertRaises(frappe.ValidationError):
			execute(self.filters)


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