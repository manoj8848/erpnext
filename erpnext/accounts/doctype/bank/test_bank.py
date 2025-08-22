# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import unittest

import frappe

from erpnext.accounts.doctype.bank.bank import Bank


class TestBank(unittest.TestCase):
	def test_on_trash_TC_ACC_196(self):
		if not frappe.db.exists("Bank", "Test Bank"):
			bank = frappe.get_doc({"doctype": "Bank", "bank_name": "Test Bank"}).insert()
		else:
			bank = frappe.get_doc("Bank", "Test Bank")

		# Create test contact linked only to this Bank
		contact = frappe.get_doc(
			{
				"doctype": "Contact",
				"first_name": "Test Contact",
				"links": [{"link_doctype": "Bank", "link_name": bank.name}],
			}
		).insert()
		address = frappe.get_doc(
			{
				"doctype": "Address",
				"address_title": "Test Address",
				"address_type": "Billing",
				"gst_category": "unregistered",
				"city": "Test City",
				"country": "United States",
				"address_line1": "Test Address Line 1",
				"links": [{"link_doctype": "Bank", "link_name": bank.name}],
			}
		).insert()
		self.assertTrue(frappe.db.exists("Contact", contact.name))
		self.assertTrue(frappe.db.exists("Address", address.name))
		Bank.on_trash(self=bank)
		self.assertFalse(frappe.db.exists("Contact", contact.name))
		self.assertFalse(frappe.db.exists("Address", address.name))
