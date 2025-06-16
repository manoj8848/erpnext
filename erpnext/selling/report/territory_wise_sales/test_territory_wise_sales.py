import frappe
from frappe.tests.utils import FrappeTestCase, change_settings, if_app_installed
from frappe.utils import add_days, today

from erpnext.accounts.doctype.payment_entry.test_payment_entry import make_test_item
from erpnext.selling.doctype.customer.test_customer import get_customer_dict
from erpnext.selling.doctype.quotation.quotation import make_sales_order
from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice

from .territory_wise_sales import execute


class TestTerritoryWiseSales(FrappeTestCase):
	def setUp(self):
		self.customer = frappe.get_doc(get_customer_dict("_Test Territory Wise Sales Customer")).insert(
			ignore_permissions=True
		)
		self.item = make_test_item("_Test Territory Sales Item")

	def tearDown(self):
		frappe.db.rollback()

	@if_app_installed("erpnext_crm")
	@change_settings("Global Defaults", {"default_currency": "INR"})
	def test_territory_wise_sales_report_TC_S_221(self):
		from erpnext_crm.erpnext_crm.doctype.opportunity.opportunity import make_quotation

		op = self.get_oppoprtunity()

		qo = make_quotation(op.name)
		qo.items[0].warehouse = "_Test Warehouse - _TC"
		qo.insert(ignore_permissions=True)
		qo.submit()

		so = make_sales_order(qo.name)
		so.delivery_date = add_days(today(), 2)
		so.insert(ignore_permissions=True)
		so.submit()

		si = make_sales_invoice(so.name)
		si.insert(ignore_permissions=True)
		si.submit()
		filters = frappe._dict(
			transaction_date=[add_days(today(), 1), add_days(today(), 3)], company=si.company
		)

		data = execute(filters=filters)

		if data[1]:
			for row in data[1]:
				if row.get("territory") == get_territory():
					self.assertEqual(row.get("territory"), "_Test Territory Wise Sales")
					self.assertEqual(row.get("quotation_amount"), 100)
					self.assertEqual(row.get("order_amount"), 100)
					self.assertEqual(row.get("billing_amount"), 100)

	def get_oppoprtunity(self):
		return frappe.get_doc(
			{
				"doctype": "Opportunity",
				"opportunity_from": "Customer",
				"party_name": self.customer.name,
				"company": "_Test Company",
				"customer_group": "All Customer Groups",
				"territory": get_territory(),
				"country": "India",
				"transaction_date": add_days(today(), 2),
				"items": [
					{
						"item_code": self.item.item_code,
						"qty": 1,
						"uom": "_Test UOM",
						"rate": 100,
						"amount": 100,
					}
				],
			}
		).insert(ignore_permissions=True, ignore_links=True)


def get_territory():
	territory = "_Test Territory Wise Sales"
	if not frappe.db.exists("Territory", territory):
		frappe.get_doc(
			{"doctype": "Territory", "territory_name": territory, "parent_territory": "All Territories"}
		).insert(ignore_permissions=True)

	return territory
