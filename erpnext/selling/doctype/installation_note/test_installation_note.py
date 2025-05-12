# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import unittest
import frappe
from erpnext.accounts.doctype.payment_entry.test_payment_entry import make_test_item
from erpnext.setup.doctype.company.test_company import create_child_company
from erpnext.accounts.doctype.payment_entry.test_payment_entry import create_customer
from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note
from erpnext.selling.doctype.sales_order.test_sales_order import make_sales_order
from erpnext.stock.doctype.delivery_note.delivery_note import make_installation_note


class TestInstallationNote(unittest.TestCase):

	def tearDown(self):
		frappe.db.rollback()

	def test_installation_note_with_serial_no_TC_S_195(self):
		serial_no = "SN-TEST-00001"
		customer = "_Test Customer"
		company = "_Test Company"
		item_code = "_Test Serialized Item"
		
		if not frappe.db.exists("Customer", customer):
			create_customer(customer, currency="INR")
		
		if not frappe.db.exists("Company", company):
			create_child_company()
		
		if not frappe.db.exists("Item", item_code):
			item = make_test_item(item_code, {
				"is_stock_item": 1,
				"has_serial_no": 1,
				"item_group": "Products",
				"stock_uom": "Nos"
			})
			item.save()
		
		if not frappe.db.exists("Serial No", serial_no):
			stock_entry = frappe.get_doc({
				"doctype": "Stock Entry",
				"stock_entry_type": "Material Receipt",
				"company": company,
				"items": [{
					"item_code": item_code,
					"qty": 1,
					"t_warehouse": "_Test Warehouse - _TC",
					"serial_no": serial_no,
					"basic_rate": 100
				}]
			})
			stock_entry.insert()
			stock_entry.submit()

		so = make_sales_order(item_code=item_code)
		dn = make_delivery_note(so.name)
		dn.items[0].qty = 1
		dn.items[0].serial_no = serial_no
		dn.submit()
		
		installation_note = make_installation_note(dn.name)
		installation_note.inst_date = frappe.utils.nowdate()
		installation_note.save()
		
		self.assertEqual(installation_note.items[0].serial_no, serial_no)
		
		installation_note.submit()
		self.assertEqual(installation_note.status, "Submitted")
		self.assertEqual(installation_note.customer, customer)
		self.assertEqual(installation_note.company, company)
		
		installation_note.cancel()
		self.assertEqual(installation_note.status, "Cancelled")
