import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from erpnext.accounts.doctype.payment_entry.test_payment_entry import make_test_item
from erpnext.selling.doctype.customer.test_customer import get_customer_dict
from erpnext.selling.doctype.sales_order.test_sales_order import make_sales_order

from .sales_person_commission_summary import execute


class TestSalesPersonCommissionSummary(FrappeTestCase):
	def setUp(self):
		item = make_test_item("_Test Sales Person Transaction Item")
		customer = frappe.get_doc(get_customer_dict("__Test Sales Person Commission Customer")).insert(
			ignore_permissions=True
		)

		self.item_code = item.item_code
		self.customer = customer.name

	def tearDown(self):
		frappe.db.rollback()

	def test_sales_person_commission_summary_TC_S_219(self):
		from erpnext.selling.report.sales_partner_commission_summary.test_sales_partner_commission_summary import (
			setup_sales_partner,
		)

		sales_partner = setup_sales_partner()
		self.selling_partner = sales_partner.get("sales_partner")
		self.sales_person = sales_partner.get("sales_person")

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
		so.append(
			"sales_team",
			{"sales_person": self.sales_person, "commission_rate": 5, "allocated_percentage": 100},
		)
		so.insert(ignore_permissions=True)
		so.submit()
		filters = {
			"sales_person": self.sales_person,
			"doc_type": "Sales Order",
			"from_date": add_days(today(), 2),
			"to_date": add_days(today(), 2),
			"customer": self.customer,
			"company": so.company,
		}
		data = execute(filters=filters)

		if data[1]:
			for row in data[1]:
				if row[1] == self.customer:
					self.assertEqual(row[1], "__Test Sales Person Commission Customer")
					self.assertEqual(row[2], "All Territories")
					self.assertEqual(row[4], 500)
					self.assertEqual(row[5], "__Test Sales Person_3")
					self.assertEqual(row[6], 100)
					self.assertEqual(row[7], "5")
					self.assertEqual(row[8], 500)
					self.assertEqual(row[9], 25)
