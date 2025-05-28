import frappe
from frappe.utils import today, add_days
from frappe.tests.utils import FrappeTestCase

from erpnext.accounts.doctype.payment_entry.test_payment_entry import make_test_item
from erpnext.selling.doctype.sales_order.test_sales_order import make_sales_order
from erpnext.selling.doctype.customer.test_customer import get_customer_dict

class TestItemWiseSalesHistory(FrappeTestCase):
	def setUp(self):
		self.item = make_test_item("_Test Item Wise Sales Item")
		self.customer = frappe.get_doc(get_customer_dict("_Test Item Wise Sales Supplier")).insert(ignore_permissions=True)
		so = make_sales_order(
			item_code = self.item.item_code,
			customer = self.customer.name,
			transaction_date = today(),
			do_not_save = True
		)
		so.insert(ignore_permissions=True)
		so.submit()

	def tearDown(self):
		frappe.db.rollback()

	def test_item_wise_sales_history_report_codecov(self):
		from .item_wise_sales_history import execute
		self.filters = {
			"company": "_Test Company",
			"from_date": add_days(today(), -1),
			"to_date": today(),
			"item": self.item.item_code,
			"customer": self.customer.name,
			"item_group": "Products",
		}
		data = execute(self.filters)
		if data[1]:
			for row in data[1]:
				self.assertEqual(row.get("item_code"), "_Test Item Wise Sales Item")
				self.assertEqual(row.get("item_group"), "Products")
				self.assertEqual(row.get("quantity"), 10)
				self.assertEqual(row.get("rate"), 100)
				self.assertEqual(row.get("amount"), 1000)
				self.assertEqual(row.get("customer"), "_Test Item Wise Sales Supplier")
				self.assertEqual(row.get("customer_group"), "_Test Customer Group")
				self.assertEqual(row.get("territory"), "All Territories")
				self.assertEqual(row.get("company"), "_Test Company")

		self.filters.update({"from_date": add_days(today(), 1), "to_date": today()})
		with self.assertRaises(frappe.ValidationError) as context:
			execute(self.filters)
		self.assertIn("From Date cannot be greater than To Date", str(context.exception))