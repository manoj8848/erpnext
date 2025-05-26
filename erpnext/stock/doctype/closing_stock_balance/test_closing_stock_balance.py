# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from erpnext.setup.doctype.company.test_company import create_child_company
from erpnext.stock.doctype.warehouse.test_warehouse import create_warehouse
from erpnext.accounts.doctype.payment_entry.test_payment_entry import make_test_item


class TestClosingStockBalance(FrappeTestCase):

	# codecov
	def test_set_status_TC_SCK_292(self):
		item_code = "Test Item"
		company = "_Test Indian Registered Company"
		warehouse = "'Stores - _TC'"
		# Ensure prerequisites exist
		if not frappe.db.exists("Company", company):
			create_child_company()

		if not frappe.db.exists("Item", item_code):
				item = make_test_item(item_code)
				item.is_stock_item = 0
				item.save()

		warehouse = frappe.get_doc(
			{
				"doctype":"Warehouse",
				"warehouse_name":warehouse,
				"parent_warehouse":"All Warehouses - _TIRC",
				"company":company
			}
		).insert(ignore_permissions=True)

		closing_balance = frappe.get_doc(
			{
			"doctype":"Closing Stock Balance",
			"naming_series":"CBAL-.#####",
			"company": company,
			"status":"Draft",
			"item_code":item,
			"include_uom":"Box",
			"warehouse":warehouse,
			"item_group":"All Item Groups",
			"warehouse_type":"Transit"
			}
		).insert(ignore_permissions=True)
		closing_balance.submit()

		closing_balance = frappe.get_doc(
			{
			"doctype":"Closing Stock Balance",
			"naming_series":"CBAL-.#####",
			"company": company,
			"status":"Draft",
			"item_code":item,
			"include_uom":"Box",
			"warehouse":warehouse,
			"item_group":"All Item Groups",
			"warehouse_type":"Transit"
			}
		).insert(ignore_permissions=True)
		closing_balance.submit()

		# Assert that the Closing Stock Balance was submitted
		self.assertEqual(closing_balance.docstatus, 1, "Closing Stock Balance should be submitted.")
		closing_balance.cancel()


		# Assert that the document is now cancelled
		self.assertEqual(closing_balance.docstatus, 2, "Closing Stock Balance should be cancelled.")
		closing_balance.regenerate_closing_balance()

	