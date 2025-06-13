import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from erpnext.accounts.doctype.payment_entry.test_payment_entry import make_test_item
from erpnext.accounts.doctype.sales_invoice.test_sales_invoice import create_sales_invoice
from erpnext.selling.doctype.customer.test_customer import get_customer_dict


class TestCustomerAcquisitionAndLoyalty(FrappeTestCase):
	def setUp(self):
		item = make_test_item("_Test Customer Acquisition Item")
		customer = frappe.get_doc(get_customer_dict("_Test Customer Acquisition Customer")).insert(
			ignore_permissions=True
		)
		self.item_code = item.item_code
		self.customer = customer.name

		si = create_sales_invoice(
			item_code=self.item_code,
			customer=self.customer,
			posting_date=add_days(today(), 2),
			do_not_save=True,
		)
		si.due_date = add_days(today(), 3)
		si.insert(ignore_permissions=True)
		si.submit()

		self.filters = {
			"view_type": "Monthly",
			"company": si.company,
			"from_date": add_days(today(), 2),
			"to_date": add_days(today(), 2),
		}

	def tearDown(self):
		frappe.db.rollback()

	def test_customer_acquisition_TS_S_211(self):
		from .customer_acquisition_and_loyalty import execute

		data = execute(self.filters)
		if data[1]:
			for row in data[1]:
				if row.get("repeat_customers") == 0:
					self.assertEqual(row.get("new_customers"), 1)
					self.assertEqual(row.get("total"), 1)
					self.assertEqual(row.get("new_customer_revenue"), 100)
					self.assertEqual(row.get("total_revenue"), 100)

		# based on Territory Wise
		self.filters.update({"view_type": "Territory Wise"})
		data_1 = execute(self.filters)
		if data_1[1]:
			for idx in data_1[1]:
				if idx.get("territory") == "All Territories":
					self.assertEqual(idx.get("new_customers"), 1)
					self.assertEqual(idx.get("new_customer_revenue"), 100)
					self.assertEqual(idx.get("repeat_customer_revenue"), 0)
					self.assertEqual(idx.get("total_revenue"), 100)
