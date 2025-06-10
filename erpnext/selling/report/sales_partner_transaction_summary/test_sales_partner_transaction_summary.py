import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from erpnext.accounts.doctype.payment_entry.test_payment_entry import make_test_item
from erpnext.selling.doctype.customer.test_customer import get_customer_dict
from erpnext.selling.doctype.sales_order.test_sales_order import make_sales_order
from erpnext.selling.report.sales_partner_commission_summary.test_sales_partner_commission_summary import (
	setup_sales_partner,
)

from .sales_partner_transaction_summary import execute


class TestSalesPartnerCommissionSummary(FrappeTestCase):
	def setUp(self):
		item = make_test_item("_Test Sales Partner Transaction Item")
		customer = frappe.get_doc(get_customer_dict("__Test Sales Partner Transaction Customer")).insert(
			ignore_permissions=True
		)
		sales_partner = setup_sales_partner()

		self.item_code = item.item_code
		self.customer = customer.name
		self.selling_partner = sales_partner.get("sales_partner")
		self.sales_person = sales_partner.get("sales_person")

	def tearDown(self):
		frappe.db.rollback()

	def test_sales_partner_transaction_summary(self):
		so = make_sales_order(
			item_code=self.item_code,
			customer=self.customer,
			transaction_date=add_days(today(), 2),
			rate=50,
			do_not_save=True,
		)
		so.customer = self.customer
		so.sales_partner = self.selling_partner
		so.commission_rate = 5
		so.append("sales_team", {"sales_person": self.sales_person, "allocated_percentage": 100})
		so.insert(ignore_permissions=True)
		so.submit()
		print(so.name)
		filters = {
			"sales_partner": self.selling_partner,
			"doctype": "Sales Order",
			"from_date": add_days(today(), 2),
			"to_date": add_days(today(), 2),
			"customer": self.customer,
			"company": so.company,
		}
		data = execute(filters=filters)

		if data[1]:
			for row in data[1]:
				if row.get("customer") == self.customer:
					self.assertEqual(row.get("customer"), "__Test Sales Partner Transaction Customer")
					self.assertEqual(row.get("territory"), "All Territories")
					self.assertEqual(row.get("currency"), "INR")
					self.assertEqual(row.get("rate"), 50)
					self.assertEqual(row.get("qty"), 10)
					self.assertEqual(row.get("amount"), 500)
					self.assertEqual(row.get("commission"), 25)
					self.assertEqual(row.get("sales_partner"), "__Test Sales Commission Partner 3")
					self.assertEqual(row.get("commission_rate"), 5)
					self.assertEqual(row.get("item_code"), "_Test Sales Partner Transaction Item")
