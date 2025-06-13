import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.accounts.doctype.payment_entry.test_payment_entry import make_test_item
from erpnext.selling.doctype.customer.test_customer import get_customer_dict_new
from erpnext.selling.report.customer_wise_item_price.customer_wise_item_price import execute


class TestCustomerWiseItemPrice(FrappeTestCase):
	def setUp(self):
		self.item = make_test_item("_Test CWIPP Item")
		self.item.is_sales_item = 1
		self.item.save()

		self.customer = frappe.get_doc(get_customer_dict_new("Test CWIP Customer")).insert(
			ignore_permissions=True
		)

		self.filters = {"item": self.item.item_code, "customer": self.customer.name}

	def tearDown(self):
		frappe.db.rollback()

	def test_report_returns_customer_specific_price_TC_S_202(self):
		data = execute(self.filters)
		for row in data[1]:
			if row.get("item_code") == self.item.item_code:
				self.assertEqual(row.get("item_code"), "_Test CWIPP Item")
				self.assertEqual(row.get("selling_rate"), 0)

	def test_validate_filters_codecov_TC_S_203(self):
		self.filters = {}
		with self.assertRaises(frappe.exceptions.ValidationError) as e:
			data = execute(self.filters)

		self.filters = {"customer": self.customer.name}
		data = execute(self.filters)
		self.assertTrue(data)