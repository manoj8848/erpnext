import frappe
from frappe.tests.utils import FrappeTestCase
from erpnext.buying.doctype.purchase_order.test_purchase_order import create_purchase_order
from erpnext.accounts.doctype.sales_invoice.test_sales_invoice import get_active_fiscal_year
from erpnext.accounts.doctype.payment_entry.test_payment_entry import make_test_item
from .purchase_order_trends import execute

class TestPurchaseOrderTrends(FrappeTestCase):
	def setUp(self):
		self.item = make_test_item("test_trends_item")
		po = create_purchase_order(item_code = self.item.item_code)
		self.filters = frappe._dict(
			company = "_Test Company",
			period = "Monthly",
			fiscal_year = get_active_fiscal_year(),
			period_based_on = "Posting Date",
			based_on = "Item"
		)

	def tearDown(self):
		frappe.db.rollback()

	def test_purchase_order_trends_report_TC_B_220(self):
		# based on item
		data = execute(self.filters)
		for row in data[1]:
			if row[0] == "test_trends_item":
				self.assertEqual(row[0], "test_trends_item")

		# based on supplier
		self.filters.update(
			{
				"based_on": "Supplier"
			}
		)
		s_data = execute(self.filters)
		for row_1 in s_data[1]:
			if row_1[0] == "_Test Supplier":
				self.assertEqual(row_1[1], "_Test Supplier Group")

		# based on supplier group
		self.filters.update(
			{
				"based_on": "Supplier Group"
			}
		)
		sg_data = execute(self.filters)
		for row_2 in sg_data[1]:
			if row_2[0] == "_Test Supplier Group":
				self.assertEqual(row_2[0], "_Test Supplier Group")

		# based on item group
		self.filters.update(
			{
				"based_on": "Item Group"
			}
		)
		ig_data = execute(self.filters)
		for row_3 in ig_data[1]:
			if row_3[0] == "_Test Item Group":
				self.assertEqual(row_3[0], "_Test Item Group")

		# based on group by item
		self.filters["group_by"] = "Item"
		g_data = execute(self.filters)
		for row_4 in g_data[1]:
			print(row_4[0])
			if row_4[0] == "_Test Item Group":
				self.assertEqual(row_4[0],  "_Test Item Group")