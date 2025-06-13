import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.accounts.doctype.payment_entry.test_payment_entry import make_test_item
from erpnext.accounts.doctype.sales_invoice.test_sales_invoice import create_sales_invoice
from erpnext.selling.doctype.customer.test_customer import get_customer_dict


class TestCustomerCreditBalance(FrappeTestCase):
	def setUp(self):
		customer = frappe.get_doc(get_customer_dict("_Test Customer Credit Balance"))
		customer.append("credit_limits", {"company": "_Test Company", "credit_limit": 100000})
		customer.insert(ignore_permissions=True)
		self.customer = customer.name

		item = make_test_item("_Test Item Credit Balance")
		self.item_code = item.item_code

	def tearDown(self):
		frappe.db.rollback()

	def test_customer_credit_balance_TC_S_210(self):
		from .customer_credit_balance import execute

		si = create_sales_invoice(item_code=self.item_code, customer=self.customer, do_not_save=True)
		si.insert(ignore_permissions=True)
		si.submit()
		self.assertEqual(si.docstatus, 1)
		filters = {"company": si.company, "customer": self.customer}
		data = execute(filters)
		if data[1]:
			for row in data[1]:
				self.assertEqual(row[0], "_Test Customer Credit Balance")
				self.assertEqual(row[1], 100000)
				self.assertEqual(row[2], 100)
				self.assertEqual(row[3], 99900)
