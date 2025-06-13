# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import unittest

import frappe
from frappe import ValidationError

# test_records = frappe.get_test_records('Bank Account')


class TestBankAccount(unittest.TestCase):
	def test_validate_iban(self):
		valid_ibans = [
			"GB82 WEST 1234 5698 7654 32",
			"DE91 1000 0000 0123 4567 89",
			"FR76 3000 6000 0112 3456 7890 189",
		]

		invalid_ibans = [
			# wrong checksum (3rd place)
			"GB72 WEST 1234 5698 7654 32",
			"DE81 1000 0000 0123 4567 89",
			"FR66 3000 6000 0112 3456 7890 189",
		]

		bank_account = frappe.get_doc({"doctype": "Bank Account"})

		try:
			bank_account.validate_iban()
		except AttributeError:
			msg = "BankAccount.validate_iban() failed for empty IBAN"
			self.fail(msg=msg)

		for iban in valid_ibans:
			bank_account.iban = iban
			try:
				bank_account.validate_iban()
			except ValidationError:
				msg = f"BankAccount.validate_iban() failed for valid IBAN {iban}"
				self.fail(msg=msg)

		for not_iban in invalid_ibans:
			bank_account.iban = not_iban
			msg = f"BankAccount.validate_iban() accepted invalid IBAN {not_iban}"
			with self.assertRaises(ValidationError, msg=msg):
				bank_account.validate_iban()

	def test_make_bank_account_TC_ACC_197(self):
		from erpnext.accounts.doctype.bank_account.bank_account import make_bank_account

		# Create test Supplier
		if not frappe.db.exists("Supplier", "Test Supplier"):
			supplier = frappe.get_doc({"doctype": "Supplier", "supplier_name": "Test Supplier"}).insert()
		else:
			supplier = frappe.get_doc("Supplier", "Test Supplier")

		result = make_bank_account("Supplier", supplier.name)
		self.assertEqual(result.party_type, "Supplier")
		self.assertEqual(result.party, supplier.name)

	def test_on_trash_TC_ACC_198(self):
		from erpnext.accounts.doctype.bank_account.bank_account import BankAccount

		if not frappe.db.exists("Bank Account", "Test Bank Account"):
			bank_account = frappe.get_doc(
				{
					"doctype": "Bank Account",
					"bank": "Test Bank",
					"account_name": "Test Account",
					"party_type": "Supplier",
					"party": "Test Supplier",
				}
			).insert()
		else:
			bank_account = frappe.get_doc("Bank Account", "Test Bank Account")
		if not frappe.db.exists("Contact", "Test Contact"):
			contact = frappe.get_doc(
				{
					"doctype": "Contact",
					"first_name": "Test Contact",
					"links": [{"link_doctype": "Bank Account", "link_name": bank_account.name}],
				}
			).insert()
		else:
			contact = frappe.get_doc("Contact", "Test Contact")

		# Create test address linked only to this Bank Account
		if not frappe.db.exists("Address", "Test Address"):
			address = frappe.get_doc(
				{
					"doctype": "Address",
					"address_title": "Test Address",
					"address_type": "Billing",
					"gst_category": "unregistered",
					"city": "Test City",
					"country": "United States",
					"address_line1": "Test Address Line 1",
					"links": [{"link_doctype": "Bank Account", "link_name": bank_account.name}],
				}
			).insert()
		else:
			address = frappe.get_doc("Address", "Test Address")
		self.assertTrue(frappe.db.exists("Contact", contact.name))
		self.assertTrue(frappe.db.exists("Address", address.name))

		BankAccount.on_trash(self=bank_account)

		self.assertFalse(frappe.db.exists("Contact", contact.name))
		self.assertFalse(frappe.db.exists("Address", address.name))
