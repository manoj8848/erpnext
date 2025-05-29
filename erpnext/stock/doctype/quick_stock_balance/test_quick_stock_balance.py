# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import frappe
import unittest
from frappe.tests.utils import FrappeTestCase
from erpnext.setup.doctype.company.test_company import create_child_company
from erpnext.stock.doctype.warehouse.test_warehouse import create_warehouse
from erpnext.accounts.doctype.payment_entry.test_payment_entry import make_test_item

class TestQuickStockBalance(FrappeTestCase):
	# codecov
	def test_get_stock_item_details_TC_SCK_312(self):
		from erpnext.stock.doctype.quick_stock_balance.quick_stock_balance import get_stock_item_details
		item_code = "Test Item"
		company = "_Test Indian Registered Company"
		warehouse = "'Stores - _TC'"
		# Ensure prerequisites exist
		if not frappe.db.exists("Company", company):
			create_child_company()

		if not frappe.db.exists("Item", item_code):
				item = make_test_item(item_code)
				item.is_stock_item = 0
				item.append("barcodes", {
                    "barcode": "123456789012",
                    "barcode_type": "UPC",
                    "uom": "Box"
                })
				item.save()


		warehouse = frappe.get_doc(
			{
				"doctype":"Warehouse",
				"warehouse_name":warehouse,
				"parent_warehouse":"All Warehouses - _TIRC",
				"company":company
			}
		).insert(ignore_permissions=True)
		date = frappe.utils.now()
		get_stock_item_details(warehouse.name, date, item=item.name, barcode="123456789012")
		
