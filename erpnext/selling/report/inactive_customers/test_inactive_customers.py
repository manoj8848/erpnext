import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from erpnext.accounts.doctype.payment_entry.test_payment_entry import make_test_item
from erpnext.selling.doctype.customer.test_customer import get_customer_dict
from erpnext.selling.doctype.sales_order.test_sales_order import make_sales_order

from .inactive_customers import execute


class TestInactiveCustomer(FrappeTestCase):
	def setUp(self):
		customer = frappe.get_doc(get_customer_dict("_Test Inactive Customer")).insert(
			ignore_permissions=True
		)
		self.customer = customer.name

		item = make_test_item("_Test Inactive Item 2")
		self.item_code = item.item_code

	def tearDown(self):
		frappe.db.rollback()

	def test_inactive_customer_report_TC_S_208(self):
		so = make_sales_order(
			customer=self.customer,
			item_code=self.item_code,
			transaction_date=add_days(today(), -2),
			do_not_save=True,
		)
		so.insert(ignore_permissions=True)
		so.submit()

		data = execute({"days_since_last_order": 2, "doctype": "Sales Order"})

		if data[1]:
			for row in data[1]:
				if row[0] == self.customer:
					self.assertEqual(row[0], "_Test Inactive Customer")
					self.assertEqual(row[1], "_Test Inactive Customer")
					self.assertEqual(row[2], "_Test Territory")
					self.assertEqual(row[3], "_Test Customer Group")
					self.assertEqual(row[4], 1)
					self.assertEqual(row[5], 1000)
					self.assertEqual(row[6], 1000)

	def test_validate_filters_TC_S_209(self):
		msg = "'Days Since Last Order' must be greater than or equal to zero"
		with self.assertRaises(frappe.ValidationError, msg=msg):
			execute()
