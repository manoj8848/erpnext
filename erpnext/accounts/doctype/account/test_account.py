# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt


import unittest

import frappe
from frappe.test_runner import make_test_records
from frappe.utils import nowdate
from erpnext.accounts.doctype.account.account import RootNotEditable

from erpnext.accounts.doctype.account.account import (
	InvalidAccountMergeError,
	merge_account,
	update_account_number,
)
from erpnext.stock import get_company_default_inventory_account, get_warehouse_account


test_dependencies = ["Company"]


class TestAccount(unittest.TestCase):
	def test_delete_account_with_children(self):
		parent_account = create_account(
			account_name="Parent Account",
			is_group=1,
			parent_account="Application of Funds (Assets) - _TC",
			company="_Test Company"
		)
		
		create_account(
			account_name="Child Account 1",
			parent_account="Parent Account - _TC",
			company="_Test Company"
		)
		
		create_account(
			account_name="Child Account 2",
			parent_account="Parent Account - _TC",
			company="_Test Company"
		)
		
		self.assertRaises(
			frappe.ValidationError,
			frappe.delete_doc,
			"Account", 
			"Parent Account - _TC"
		)
		
		frappe.delete_doc("Account", "Child Account 1 - _TC")
		frappe.delete_doc("Account", "Child Account 2 - _TC")

	def test_rename_account(self):
		if frappe.db.exists("Account", "1211-11-4 - 6 - - Debtors 1 - Test - - _TC"):
			frappe.delete_doc("Account", "1211-11-4 - 6 - - Debtors 1 - Test - - _TC")

		if not frappe.db.exists("Account", "1210 - Debtors - _TC"):
			acc = frappe.new_doc("Account")
			acc.account_name = "Debtors"
			acc.parent_account = "Accounts Receivable - _TC"
			acc.account_number = "1210"
			acc.company = "_Test Company"
			acc.insert(ignore_permissions=True)

			account_number, account_name = frappe.db.get_value(
				"Account", "1210 - Debtors - _TC", ["account_number", "account_name"]
			)
			self.assertEqual(account_number, "1210")
			self.assertEqual(account_name, "Debtors")

		new_account_number = "1211-11-4 - 6 - "
		new_account_name = "Debtors 1 - Test - "

		update_account_number("1210 - Debtors - _TC", new_account_name, new_account_number)

		new_acc = frappe.db.get_value(
			"Account",
			"1211-11-4 - 6 - - Debtors 1 - Test - - _TC",
			["account_name", "account_number"],
			as_dict=1,
		)

		self.assertEqual(new_acc.account_name, "Debtors 1 - Test -")
		self.assertEqual(new_acc.account_number, "1211-11-4 - 6 -")

		frappe.delete_doc("Account", "1211-11-4 - 6 - Debtors 1 - Test - - _TC")

	def test_merge_account(self):
		create_account(
			account_name="Current Assets",
			is_group=1,
			parent_account="Application of Funds (Assets) - _TC",
			company="_Test Company",
		)

		create_account(
			account_name="Securities and Deposits",
			is_group=1,
			parent_account="Current Assets - _TC",
			company="_Test Company",
		)

		create_account(
			account_name="Earnest Money",
			parent_account="Securities and Deposits - _TC",
			company="_Test Company",
		)

		create_account(
			account_name="Cash In Hand",
			is_group=1,
			parent_account="Current Assets - _TC",
			company="_Test Company",
		)

		create_account(
			account_name="Receivable INR",
			parent_account="Current Assets - _TC",
			company="_Test Company",
			account_currency="INR",
		)

		create_account(
			account_name="Receivable USD",
			parent_account="Current Assets - _TC",
			company="_Test Company",
			account_currency="USD",
		)

		parent = frappe.db.get_value("Account", "Earnest Money - _TC", "parent_account")

		self.assertEqual(parent, "Securities and Deposits - _TC")

		merge_account("Securities and Deposits - _TC", "Cash In Hand - _TC")

		parent = frappe.db.get_value("Account", "Earnest Money - _TC", "parent_account")

		# Parent account of the child account changes after merging
		self.assertEqual(parent, "Cash In Hand - _TC")

		# Old account doesn't exist after merging
		self.assertFalse(frappe.db.exists("Account", "Securities and Deposits - _TC"))

		# Raise error as is_group property doesn't match
		self.assertRaises(
			InvalidAccountMergeError,
			merge_account,
			"Current Assets - _TC",
			"Accumulated Depreciation - _TC",
		)

		# Raise error as root_type property doesn't match
		self.assertRaises(
			InvalidAccountMergeError,
			merge_account,
			"Capital Stock - _TC",
			"Softwares - _TC",
		)

		# Raise error as currency doesn't match
		self.assertRaises(
			InvalidAccountMergeError,
			merge_account,
			"Receivable INR - _TC",
			"Receivable USD - _TC",
		)

	def test_account_sync(self):
		frappe.local.flags.pop("ignore_root_company_validation", None)

		acc = frappe.new_doc("Account")
		acc.account_name = "Test Sync Account"
		acc.parent_account = "Temporary Accounts - _TC3"
		acc.company = "_Test Company 3"
		acc.insert(ignore_permissions=True)

		acc_tc_4 = frappe.db.get_value(
			"Account", {"account_name": "Test Sync Account", "company": "_Test Company 4"}
		)
		acc_tc_5 = frappe.db.get_value(
			"Account", {"account_name": "Test Sync Account", "company": "_Test Company 5"}
		)
		self.assertEqual(acc_tc_4, "Test Sync Account - _TC4")
		self.assertEqual(acc_tc_5, "Test Sync Account - _TC5")

	def test_add_account_to_a_group(self):
		frappe.db.set_value("Account", "Office Rent - _TC3", "is_group", 1)

		acc = frappe.new_doc("Account")
		acc.account_name = "Test Group Account"
		acc.parent_account = "Office Rent - _TC3"
		acc.company = "_Test Company 3"
		self.assertRaises(frappe.ValidationError, acc.insert)

		frappe.db.set_value("Account", "Office Rent - _TC3", "is_group", 0)

	def test_account_rename_sync(self):
		frappe.local.flags.pop("ignore_root_company_validation", None)

		acc = frappe.new_doc("Account")
		acc.account_name = "Test Rename Account"
		acc.parent_account = "Temporary Accounts - _TC3"
		acc.company = "_Test Company 3"
		acc.insert(ignore_permissions=True)

		# Rename account in parent company
		update_account_number(acc.name, "Test Rename Sync Account", "1234")

		# Check if renamed in children
		self.assertTrue(
			frappe.db.exists(
				"Account",
				{
					"account_name": "Test Rename Sync Account",
					"company": "_Test Company 4",
					"account_number": "1234",
				},
			)
		)
		self.assertTrue(
			frappe.db.exists(
				"Account",
				{
					"account_name": "Test Rename Sync Account",
					"company": "_Test Company 5",
					"account_number": "1234",
				},
			)
		)

		frappe.delete_doc("Account", "1234 - Test Rename Sync Account - _TC3")
		frappe.delete_doc("Account", "1234 - Test Rename Sync Account - _TC4")
		frappe.delete_doc("Account", "1234 - Test Rename Sync Account - _TC5")

	def test_account_currency_sync(self):
		"""
		In a parent->child company setup, child should inherit parent account currency if explicitly specified.
		"""

		make_test_records("Company")

		frappe.local.flags.pop("ignore_root_company_validation", None)

		def create_bank_account():
			acc = frappe.new_doc("Account")
			acc.account_name = "_Test Bank JPY"

			acc.parent_account = "Temporary Accounts - _TC6"
			acc.company = "_Test Company 6"
			return acc

		acc = create_bank_account()
		# Explicitly set currency
		acc.account_currency = "JPY"
		acc.insert(ignore_permissions=True)
		self.assertTrue(
			frappe.db.exists(
				{
					"doctype": "Account",
					"account_name": "_Test Bank JPY",
					"account_currency": "JPY",
					"company": "_Test Company 7",
				}
			)
		)

		frappe.delete_doc("Account", "_Test Bank JPY - _TC6")
		frappe.delete_doc("Account", "_Test Bank JPY - _TC7")

		acc = create_bank_account()
		# default currency is used
		acc.insert(ignore_permissions=True)
		self.assertTrue(
			frappe.db.exists(
				{
					"doctype": "Account",
					"account_name": "_Test Bank JPY",
					"account_currency": "USD",
					"company": "_Test Company 7",
				}
			)
		)

		frappe.delete_doc("Account", "_Test Bank JPY - _TC6")
		frappe.delete_doc("Account", "_Test Bank JPY - _TC7")

	def test_child_company_account_rename_sync(self):
		frappe.local.flags.pop("ignore_root_company_validation", None)

		acc = frappe.new_doc("Account")
		acc.account_name = "Test Group Account"
		acc.parent_account = "Temporary Accounts - _TC3"
		acc.is_group = 1
		acc.company = "_Test Company 3"
		acc.insert(ignore_permissions=True)

		self.assertTrue(
			frappe.db.exists("Account", {"account_name": "Test Group Account", "company": "_Test Company 4"})
		)
		self.assertTrue(
			frappe.db.exists("Account", {"account_name": "Test Group Account", "company": "_Test Company 5"})
		)

		# Try renaming child company account
		acc_tc_5 = frappe.db.get_value(
			"Account", {"account_name": "Test Group Account", "company": "_Test Company 5"}
		)
		self.assertRaises(frappe.ValidationError, update_account_number, acc_tc_5, "Test Modified Account")

		# Rename child company account with allow_account_creation_against_child_company enabled
		frappe.db.set_value("Company", "_Test Company 5", "allow_account_creation_against_child_company", 1)

		update_account_number(acc_tc_5, "Test Modified Account")
		self.assertTrue(
			frappe.db.exists(
				"Account", {"name": "Test Modified Account - _TC5", "company": "_Test Company 5"}
			)
		)

		frappe.db.set_value("Company", "_Test Company 5", "allow_account_creation_against_child_company", 0)

		to_delete = [
			"Test Group Account - _TC3",
			"Test Group Account - _TC4",
			"Test Modified Account - _TC5",
		]
		for doc in to_delete:
			frappe.delete_doc("Account", doc)

	def test_validate_account_currency(self):
		from erpnext.accounts.doctype.journal_entry.test_journal_entry import make_journal_entry

		if not frappe.db.get_value("Account", "Test Currency Account - _TC"):
			acc = frappe.new_doc("Account")
			acc.account_name = "Test Currency Account"
			acc.parent_account = "Tax Assets - _TC"
			acc.company = "_Test Company"
			acc.insert(ignore_permissions=True)
		else:
			acc = frappe.get_doc("Account", "Test Currency Account - _TC")

		self.assertEqual(acc.account_currency, "INR")

		# Make a JV against this account
		make_journal_entry("Test Currency Account - _TC", "Miscellaneous Expenses - _TC", 100, submit=True)

		acc.account_currency = "USD"
		self.assertRaises(frappe.ValidationError, acc.save)

	def test_account_balance(self):
		from erpnext.accounts.utils import get_balance_on

		if not frappe.db.exists("Account", "Test Percent Account %5 - _TC"):
			acc = frappe.new_doc("Account")
			acc.account_name = "Test Percent Account %5"
			acc.parent_account = "Tax Assets - _TC"
			acc.company = "_Test Company"
			acc.insert(ignore_permissions=True)

		balance = get_balance_on(account="Test Percent Account %5 - _TC", date=nowdate())
		self.assertEqual(balance, 0)

	def test_allow_unverified_chart_TC_ACC_167(self):
		company = make_company(company_name="_Test Company")
		frappe.local.flags.allow_unverified_charts = True
		if frappe.db.exists("Account", "Test Account - _TC"):
			frappe.delete_doc("Account", "Test Account - _TC", force=1)
		account = frappe.new_doc("Account")
		account.account_name = "Test Account"
		account.company = company.name
		account.parent_account = "Cash In Hand - _TC"
		account.insert(ignore_permissions=True)
		self.assertEqual(account.parent_account, "Cash In Hand - _TC")

	def test_validate_parent_child_account_type_TC_ACC_168(self):
		company = make_company(company_name="_Test Company")
		account_type = "Direct Income"
		create_account(
		account_name="Test Parent Account 470",  
		parent_account="Cash In Hand - _TC", 
		company=company.name,
		account_type=account_type,
		account_currency="INR",
		is_group=1
		)
		child_account = frappe.get_doc(dict(
			doctype = "Account",
			account_name = "Test Child Account",
			parent_account = "Test Parent Account 470 - _TC",
			company = company.name,
			account_type = account_type,
			account_currency = "INR",
			is_group = 0
		))
		with self.assertRaises(frappe.ValidationError, msg=f"Only Parent can be of type {account_type}"):
			child_account.save()

	def test_validate_parent_account_not_assign_TC_ACC_169(self):
		company = make_company(company_name="_Test Company")
		create_account(
		account_name="Test Parent Account 013",  
		parent_account="Cash In Hand - _TC", 
		company=company.name,
		account_type="Direct Income",
		account_currency="INR",
		is_group=1
		)
		if frappe.db.exists("Account", "Test Account 123 - _TC"):
			frappe.delete_doc("Account", "Test Account 123 - _TC", force=1)
		account = frappe.new_doc("Account")
		account.account_name = "Test Account 123"
		account.is_group = 0
		account.parent_account = "Test Parent Account 013 - _TC"
		account.company = company.name
		account.save()
		account.parent_account = account.name
		with self.assertRaises(frappe.ValidationError, msg=f"Account {account.name}: You can not assign itself as parent account"):
			account.save()
	
	def test_validate_parent_account_is_group_TC_ACC_170(self):
		company = make_company(company_name="_Test Company")
		create_account(
		account_name="Test Parent Account 01",  
		parent_account="Cash In Hand - _TC", 
		company=company.name,
		account_type="Direct Income",
		account_currency="INR",
		is_group=0
		)
		if frappe.db.exists("Account", "Test Account 123 - _TC"):
			frappe.delete_doc("Account", "Test Account 123 - _TC", force=1)
		account = frappe.new_doc("Account")
		account.account_name = "Test Account 123"
		account.is_group = 0
		account.parent_account = "Test Parent Account 01 - _TC"
		account.company = company.name
		with self.assertRaises(frappe.ValidationError, msg="Account Test Account 123 - _TC: Parent account Test Parent Account 01 - _TC can not be a ledger"):
			account.save()
	
	def test_validate_parent_account_for_company_TC_ACC_171(self):
		company = make_company(company_name="_Test Company")
		company_2 = make_company(company_name="Test Company New")
		create_account(
		account_name="Test Parent Account 012",  
		parent_account="Cash In Hand - TCN", 
		company=company_2.name,
		account_type="Direct Income",
		account_currency="INR",
		is_group=1
		)
		if frappe.db.exists("Account", "Test Account 123 - _TC"):
			frappe.delete_doc("Account", "Test Account 123 - _TC", force=1)
		account = frappe.new_doc("Account")
		account.account_name = "Test Account 123"
		account.is_group = 0
		account.parent_account = "Test Parent Account 012 - TCN"
		account.company = company.name
		with self.assertRaises(frappe.ValidationError, msg="Account Test Account 123 - _TC: Parent account Test Parent Account 012 - TCN does not belong to company: _Test Company"):
			account.save()
	
	def test_set_root_and_report_type_TC_ACC_172(self):
		company = make_company(company_name="_Test Company")
		if frappe.db.exists("Account", "Parent Account 4 - _TC"):
			frappe.delete_doc("Account", "Parent Account 4 - _TC", force=1)
		account = frappe.new_doc("Account")
		account.account_name = "Parent Account 4"
		account.company = company.name
		account.account_type = "Cash"
		account.parent_account = "Cash In Hand - _TC"
		account.is_group = 1
		account.save()
		account.db_set("root_type", "Liability")
		account.db_set("report_type", "Profit and Loss")
		account.save()
		account.reload()
		self.assertEqual(account.is_group, 1)
		self.assertEqual(account.account_type, "Cash")

	def test_validate_receivable_payable_account_type_TC_ACC_173(self):
		from erpnext.stock.doctype.warehouse.test_warehouse import create_warehouse
		from erpnext.buying.doctype.supplier.test_supplier import create_supplier
		from erpnext.stock.doctype.item.test_item import create_item
		company = make_company(company_name="_Test Company")
		item_code = "_Test Item"
		supplier = "_Test Supplier"
		
		create_warehouse(
			warehouse_name="_Test Warehouse - _TC",
			properties={"parent_warehouse": "All Warehouses - _TC", "account": "Cost of Goods Sold - _TC"},
			company="_Test Company",
		)
		create_supplier(supplier_name=supplier, default_currency="INR")
		item = create_item(item_code = item_code,valuation_rate=100)
		pi = frappe.new_doc("Purchase Invoice")
		pi.supplier = supplier
		pi.company=company.name
		pi.currency="INR"
		pi.append("items", {
			"item_code": item.item_code,
			"qty": 8,
			"rate": 100
		})
		pi.save()
		pi.submit()
		account = frappe.get_doc("Account", "Creditors - _TC")
		account.account_type = "Cash"
		account.save()
		account.db_set("account_type", "Payable")
		self.assertEqual(account.account_type, "Payable")
	
	def test_validate_root_details_TC_ACC_174(self):
		company = make_company(company_name="_Test Company")
		if frappe.db.exists("Account", "Root Account - _TC"):
			frappe.delete_doc("Account", "Root Account - _TC", force=1)
		account = frappe.get_doc(
					{
					"doctype": "Account",
					"account_name": "Root Account",
					"root_type": "Asset",
					"is_group": "1",
					"company": company.name,
					}
				).insert(ignore_mandatory=True)
		with self.assertRaises(RootNotEditable, msg="Root cannot be edited."):
			account.save()
	
	def test_validate_root_account_must_be_group_TC_ACC_175(self):
		if frappe.db.exists("Account", "Testing Root - _TC"):
			frappe.delete_doc("Account", "Testing Root - _TC", force=1)
		company = make_company(company_name="_Test Company")
		account = frappe.new_doc("Account")
		account.account_name = "Testing Root"
		account.company = company.name
		account.account_type = "Cash"
		account.parent_account = "Cash In Hand - _TC"
		account.is_group = 0
		account.save()
		account.parent_account = ""
		with self.assertRaises(frappe.ValidationError, msg="The root account Testing Root - _TC must be a group"):
			account.save()

	def test_with_child_node_convert_group_to_ledger_TC_ACC_176(self):
		company = make_company(company_name="Test Company")
		create_account(
			account_name="Test Parent Account 147",  
			parent_account="Cash In Hand - TC", 
			company=company.name,
			account_type="Direct Income",
			account_currency="INR",
			is_group=1
		)
		if frappe.db.exists("Account", "Test Child - TC"):
			frappe.delete_doc("Account", "Test Child - TC", force=1)
		frappe.get_doc({
            "doctype": "Account",
            "account_name": "Test Child",
            "parent_account": "Test Parent Account 147 - TC",
            "is_group": 0,
            "company": company.name
        }).insert()
		parent_doc = frappe.get_doc("Account", "Test Parent Account 147 - TC")
		with self.assertRaises(frappe.ValidationError, msg="Account with child nodes cannot be converted to ledger"):
			parent_doc.convert_group_to_ledger()

	def test_convert_group_to_ledger_with_ledger_exists_TC_ACC_177(self):
		from erpnext.stock.doctype.warehouse.test_warehouse import create_warehouse
		from erpnext.buying.doctype.supplier.test_supplier import create_supplier
		from erpnext.stock.doctype.item.test_item import create_item
		company = make_company(company_name="_Test Company")
		item_code = "_Test Item"
		supplier = "_Test Supplier"
		
		create_warehouse(
			warehouse_name="_Test Warehouse - _TC",
			properties={"parent_warehouse": "All Warehouses - _TC", "account": "Cost of Goods Sold - _TC"},
			company="_Test Company",
		)
		create_supplier(supplier_name=supplier, default_currency="INR")
		item = create_item(item_code = item_code,valuation_rate=100)
		pi = frappe.new_doc("Purchase Invoice")
		pi.supplier = supplier
		pi.company=company.name
		pi.currency="INR"
		pi.append("items", {
			"item_code": item.item_code,
			"qty": 8,
			"rate": 100
		})
		pi.save()
		pi.submit()
		account = frappe.get_doc("Account", "Creditors - _TC")
		with self.assertRaises(frappe.ValidationError, msg="Account with existing transaction cannot be converted to ledger"):
			account.convert_group_to_ledger()

	def test_should_convert_to_ledger_TC_ACC_178(self):
		company = make_company(company_name="Test Company")
		if frappe.db.exists("Account", "Test Convertible Account - TC"):
			frappe.delete_doc("Account", "Test Convertible Account - TC", force=1)
		account = frappe.get_doc({
            "doctype": "Account",
            "account_name": "Test Convertible Account",
            "is_group": 1,
            "company": company.name,
			"parent_account":"Accounts Receivable - TC",
			"root_type": "Asset"
        }).insert()
		account.convert_group_to_ledger()
		account.reload()
		self.assertEqual(account.is_group, 0)

def _make_test_records(verbose=None):
	from frappe.test_runner import make_test_objects

	accounts = [
		# [account_name, parent_account, is_group]
		["_Test Bank", "Bank Accounts", 0, "Bank", None],
		["_Test Bank USD", "Bank Accounts", 0, "Bank", "USD"],
		["_Test Bank EUR", "Bank Accounts", 0, "Bank", "EUR"],
		["_Test Cash", "Cash In Hand", 0, "Cash", None],
		["_Test Account Stock Expenses", "Direct Expenses", 1, None, None],
		["_Test Account Shipping Charges", "_Test Account Stock Expenses", 0, "Chargeable", None],
		["_Test Account Customs Duty", "_Test Account Stock Expenses", 0, "Tax", None],
		["_Test Account Insurance Charges", "_Test Account Stock Expenses", 0, "Chargeable", None],
		["_Test Account Stock Adjustment", "_Test Account Stock Expenses", 0, "Stock Adjustment", None],
		["_Test Employee Advance", "Current Liabilities", 0, None, None],
		["_Test Account Tax Assets", "Current Assets", 1, None, None],
		["_Test Account VAT", "_Test Account Tax Assets", 0, "Tax", None],
		["_Test Account Service Tax", "_Test Account Tax Assets", 0, "Tax", None],
		["_Test Account Reserves and Surplus", "Current Liabilities", 0, None, None],
		["_Test Account Cost for Goods Sold", "Expenses", 0, None, None],
		["_Test Account Excise Duty", "_Test Account Tax Assets", 0, "Tax", None],
		["_Test Account Education Cess", "_Test Account Tax Assets", 0, "Tax", None],
		["_Test Account S&H Education Cess", "_Test Account Tax Assets", 0, "Tax", None],
		["_Test Account CST", "Direct Expenses", 0, "Tax", None],
		["_Test Account Discount", "Direct Expenses", 0, None, None],
		["_Test Write Off", "Indirect Expenses", 0, None, None],
		["_Test Exchange Gain/Loss", "Indirect Expenses", 0, None, None],
		["_Test Account Sales", "Direct Income", 0, None, None],
		# related to Account Inventory Integration
		["_Test Account Stock In Hand", "Current Assets", 0, None, None],
		# fixed asset depreciation
		["_Test Fixed Asset", "Current Assets", 0, "Fixed Asset", None],
		["_Test Accumulated Depreciations", "Current Assets", 0, "Accumulated Depreciation", None],
		["_Test Depreciations", "Expenses", 0, "Depreciation", None],
		["_Test Gain/Loss on Asset Disposal", "Expenses", 0, None, None],
		# Receivable / Payable Account
		["_Test Receivable", "Current Assets", 0, "Receivable", None],
		["_Test Payable", "Current Liabilities", 0, "Payable", None],
		["_Test Receivable USD", "Current Assets", 0, "Receivable", "USD"],
		["_Test Payable USD", "Current Liabilities", 0, "Payable", "USD"],
	]

	for company, abbr in [
		["_Test Company", "_TC"],
		["_Test Company 1", "_TC1"],
		["_Test Company with perpetual inventory", "TCP1"],
	]:
		test_objects = make_test_objects(
			"Account",
			[
				{
					"doctype": "Account",
					"account_name": account_name,
					"parent_account": parent_account + " - " + abbr,
					"company": company,
					"is_group": is_group,
					"account_type": account_type,
					"account_currency": currency,
				}
				for account_name, parent_account, is_group, account_type, currency in accounts
			],
		)

	return test_objects

def make_company(company_name, **kwargs):
	company = frappe._dict()
	if not frappe.db.exists("Company", company_name):
		company = frappe.get_doc(dict(
			doctype = "Company",
			company_name = company_name,
			company_type = "Company",
			default_currency = kwargs.get("default_currency") or "INR",
			country = kwargs.get("country") or "India",
		)).insert(ignore_permissions=True)
	else:
		company = frappe.get_doc("Company", company_name)
	return company

def get_inventory_account(company, warehouse=None):
	account = None
	if warehouse:
		account = get_warehouse_account(frappe.get_doc("Warehouse", warehouse))
	else:
		account = get_company_default_inventory_account(company)

	return account


def create_account(**kwargs):
	account = frappe.db.get_value(
		"Account", filters={"account_name": kwargs.get("account_name"), "company": kwargs.get("company")}
	)
	if account:
		account = frappe.get_doc("Account", account)
		account.update(
			dict(
				is_group=kwargs.get("is_group", 0),
				parent_account=kwargs.get("parent_account"),
			)
		)
		account.save()
		return account.name
	else:
		account = frappe.get_doc(
			dict(
				doctype="Account",
				is_group=kwargs.get("is_group", 0),
				account_name=kwargs.get("account_name"),
				account_type=kwargs.get("account_type"),
				parent_account=kwargs.get("parent_account"),
				company=kwargs.get("company"),
				account_currency=kwargs.get("account_currency"),
			)
		)

		account.save()
		return account.name
