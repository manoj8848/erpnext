# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import unittest
import frappe
from erpnext.accounts.doctype.sales_invoice.test_sales_invoice import create_company
from erpnext.accounts.doctype.payment_entry.test_payment_entry import create_customer
from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note
from erpnext.selling.doctype.sales_order.test_sales_order import make_sales_order
from erpnext.stock.doctype.delivery_note.delivery_note import make_installation_note
from erpnext.stock.doctype.item.test_item import make_item


class TestInstallationNote(unittest.TestCase):

	def setUp(self):
		self.serial_no = "SN-TEST-00001"
		self.customer = "_Test Customer"
		self.company = "_Test Company"
		self.item_code = "_Test Serialized Item"
		self.warehouse = "_Test Warehouse - _TC"

		create_customer(self.customer, currency="INR")
		create_company(self.company)

		item = make_item(self.item_code, {
			"is_stock_item": 1,
			"has_serial_no": 1,
			"item_group": "Products",
			"stock_uom": "Nos"
		})
		item.save()

		if not frappe.db.exists("Serial No", self.serial_no):
			stock_entry = frappe.get_doc({
				"doctype": "Stock Entry",
				"stock_entry_type": "Material Receipt",
				"company": self.company,
				"items": [{
					"item_code": self.item_code,
					"qty": 1,
					"t_warehouse": self.warehouse,
					"serial_no": self.serial_no,
					"basic_rate": 100
				}]
			})
			stock_entry.insert()
			stock_entry.submit()

	def tearDown(self):
		frappe.db.rollback()

	def test_installation_note_with_serial_no_TC_S_195(self):
		so = make_sales_order(item_code=self.item_code)
		dn = make_delivery_note(so.name)
		dn.items[0].qty = 1
		dn.items[0].serial_no = self.serial_no
		dn.submit()

		installation_note = make_installation_note(dn.name)
		installation_note.inst_date = frappe.utils.nowdate()
		installation_note.save()

		self.assertEqual(installation_note.items[0].serial_no, self.serial_no)

		installation_note.submit()
		self.assertEqual(installation_note.status, "Submitted")
		self.assertEqual(installation_note.customer, self.customer)
		self.assertEqual(installation_note.company, self.company)

		installation_note.cancel()
		self.assertEqual(installation_note.status, "Cancelled")
