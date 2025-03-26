# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt


import unittest

import frappe
from frappe.tests.utils import change_settings
from frappe.utils import flt, nowdate

from erpnext.accounts.doctype.account.test_account import get_inventory_account
from erpnext.accounts.doctype.journal_entry.journal_entry import StockAccountInvalidTransaction
from erpnext.exceptions import InvalidAccountCurrency


class TestJournalEntry(unittest.TestCase):
	@change_settings("Accounts Settings", {"unlink_payment_on_cancellation_of_invoice": 1})
	def test_journal_entry_with_against_jv(self):
		jv_invoice = frappe.copy_doc(test_records[2])
		base_jv = frappe.copy_doc(test_records[0])
		self.jv_against_voucher_testcase(base_jv, jv_invoice)

	def test_jv_against_sales_order(self):
		from erpnext.selling.doctype.sales_order.test_sales_order import make_sales_order

		sales_order = make_sales_order(do_not_save=True)
		base_jv = frappe.copy_doc(test_records[0])
		self.jv_against_voucher_testcase(base_jv, sales_order)

	def test_jv_against_purchase_order(self):
		from erpnext.buying.doctype.purchase_order.test_purchase_order import create_purchase_order

		purchase_order = create_purchase_order(do_not_save=True)
		base_jv = frappe.copy_doc(test_records[1])
		self.jv_against_voucher_testcase(base_jv, purchase_order)

	def jv_against_voucher_testcase(self, base_jv, test_voucher):
		dr_or_cr = "credit" if test_voucher.doctype in ["Sales Order", "Journal Entry"] else "debit"

		test_voucher.insert()
		test_voucher.submit()

		if test_voucher.doctype == "Journal Entry":
			self.assertTrue(
				frappe.db.sql(
					"""select name from `tabJournal Entry Account`
				where account = %s and docstatus = 1 and parent = %s""",
					("Debtors - _TC", test_voucher.name),
				)
			)

		self.assertFalse(
			frappe.db.sql(
				"""select name from `tabJournal Entry Account`
			where reference_type = %s and reference_name = %s""",
				(test_voucher.doctype, test_voucher.name),
			)
		)

		base_jv.get("accounts")[0].is_advance = (
			"Yes" if (test_voucher.doctype in ["Sales Order", "Purchase Order"]) else "No"
		)
		base_jv.get("accounts")[0].set("reference_type", test_voucher.doctype)
		base_jv.get("accounts")[0].set("reference_name", test_voucher.name)
		base_jv.insert()
		base_jv.submit()

		submitted_voucher = frappe.get_doc(test_voucher.doctype, test_voucher.name)

		self.assertTrue(
			frappe.db.sql(
				f"""select name from `tabJournal Entry Account`
			where reference_type = %s and reference_name = %s and {dr_or_cr}=400""",
				(submitted_voucher.doctype, submitted_voucher.name),
			)
		)

		if base_jv.get("accounts")[0].is_advance == "Yes":
			self.advance_paid_testcase(base_jv, submitted_voucher, dr_or_cr)
		self.cancel_against_voucher_testcase(submitted_voucher)

	def advance_paid_testcase(self, base_jv, test_voucher, dr_or_cr):
		# Test advance paid field
		advance_paid = frappe.db.sql(
			"""select advance_paid from `tab{}`
					where name={}""".format(test_voucher.doctype, "%s"),
			(test_voucher.name),
		)
		payment_against_order = base_jv.get("accounts")[0].get(dr_or_cr)

		self.assertTrue(flt(advance_paid[0][0]) == flt(payment_against_order))

	def cancel_against_voucher_testcase(self, test_voucher):
		if test_voucher.doctype == "Journal Entry":
			# if test_voucher is a Journal Entry, test cancellation of test_voucher
			test_voucher.cancel()
			self.assertFalse(
				frappe.db.sql(
					"""select name from `tabJournal Entry Account`
				where reference_type='Journal Entry' and reference_name=%s""",
					test_voucher.name,
				)
			)

		elif test_voucher.doctype in ["Sales Order", "Purchase Order"]:
			# if test_voucher is a Sales Order/Purchase Order, test error on cancellation of test_voucher
			frappe.db.set_single_value(
				"Accounts Settings", "unlink_advance_payment_on_cancelation_of_order", 0
			)
			submitted_voucher = frappe.get_doc(test_voucher.doctype, test_voucher.name)
			self.assertRaises(frappe.LinkExistsError, submitted_voucher.cancel)

	def test_jv_against_stock_account(self):
		company = "_Test Company with perpetual inventory"
		stock_account = get_inventory_account(company)

		from erpnext.accounts.utils import get_stock_and_account_balance

		account_bal, stock_bal, warehouse_list = get_stock_and_account_balance(
			stock_account, nowdate(), company
		)
		diff = flt(account_bal) - flt(stock_bal)

		if not diff:
			diff = 100

		jv = frappe.new_doc("Journal Entry")
		jv.company = company
		jv.posting_date = nowdate()
		jv.append(
			"accounts",
			{
				"account": stock_account,
				"cost_center": "Main - TCP1",
				"debit_in_account_currency": 0 if diff > 0 else abs(diff),
				"credit_in_account_currency": diff if diff > 0 else 0,
			},
		)

		jv.append(
			"accounts",
			{
				"account": "Stock Adjustment - TCP1",
				"cost_center": "Main - TCP1",
				"debit_in_account_currency": diff if diff > 0 else 0,
				"credit_in_account_currency": 0 if diff > 0 else abs(diff),
			},
		)

		if account_bal == stock_bal:
			self.assertRaises(StockAccountInvalidTransaction, jv.save)
			frappe.db.rollback()
		else:
			jv.submit()
			jv.cancel()

	def test_multi_currency(self):
		jv = make_journal_entry("_Test Bank USD - _TC", "_Test Bank - _TC", 100, exchange_rate=50, save=False)

		jv.get("accounts")[1].credit_in_account_currency = 5000
		jv.submit()

		self.voucher_no = jv.name

		self.fields = [
			"account",
			"account_currency",
			"debit",
			"debit_in_account_currency",
			"credit",
			"credit_in_account_currency",
		]

		self.expected_gle = [
			{
				"account": "_Test Bank - _TC",
				"account_currency": "INR",
				"debit": 0,
				"debit_in_account_currency": 0,
				"credit": 5000,
				"credit_in_account_currency": 5000,
			},
			{
				"account": "_Test Bank USD - _TC",
				"account_currency": "USD",
				"debit": 5000,
				"debit_in_account_currency": 100,
				"credit": 0,
				"credit_in_account_currency": 0,
			},
		]

		self.check_gl_entries()

		# cancel
		jv.cancel()

		gle = frappe.db.sql(
			"""select name from `tabGL Entry`
			where voucher_type='Sales Invoice' and voucher_no=%s""",
			jv.name,
		)

		self.assertFalse(gle)

	def test_reverse_journal_entry(self):
		from erpnext.accounts.doctype.journal_entry.journal_entry import make_reverse_journal_entry

		jv = make_journal_entry("_Test Bank USD - _TC", "Sales - _TC", 100, exchange_rate=50, save=False)

		jv.get("accounts")[1].credit_in_account_currency = 5000
		jv.get("accounts")[1].exchange_rate = 1
		jv.submit()

		rjv = make_reverse_journal_entry(jv.name)
		rjv.posting_date = nowdate()
		rjv.submit()

		self.voucher_no = rjv.name

		self.fields = [
			"account",
			"account_currency",
			"debit",
			"credit",
			"debit_in_account_currency",
			"credit_in_account_currency",
		]

		self.expected_gle = [
			{
				"account": "_Test Bank USD - _TC",
				"account_currency": "USD",
				"debit": 0,
				"debit_in_account_currency": 0,
				"credit": 5000,
				"credit_in_account_currency": 100,
			},
			{
				"account": "Sales - _TC",
				"account_currency": "INR",
				"debit": 5000,
				"debit_in_account_currency": 5000,
				"credit": 0,
				"credit_in_account_currency": 0,
			},
		]

		self.check_gl_entries()

	def test_disallow_change_in_account_currency_for_a_party(self):
		# create jv in USD
		jv = make_journal_entry("_Test Bank USD - _TC", "_Test Receivable USD - _TC", 100, save=False)

		jv.accounts[1].update({"party_type": "Customer", "party": "_Test Customer USD"})

		jv.submit()

		# create jv in USD, but account currency in INR
		jv = make_journal_entry("_Test Bank - _TC", "Debtors - _TC", 100, save=False)

		jv.accounts[1].update({"party_type": "Customer", "party": "_Test Customer USD"})

		self.assertRaises(InvalidAccountCurrency, jv.submit)

		# back in USD
		jv = make_journal_entry("_Test Bank USD - _TC", "_Test Receivable USD - _TC", 100, save=False)

		jv.accounts[1].update({"party_type": "Customer", "party": "_Test Customer USD"})

		jv.submit()

	def test_inter_company_jv(self):
		jv = make_journal_entry(
			"Sales Expenses - _TC",
			"Buildings - _TC",
			100,
			posting_date=nowdate(),
			cost_center="Main - _TC",
			save=False,
		)
		jv.voucher_type = "Inter Company Journal Entry"
		jv.multi_currency = 0
		jv.insert()
		jv.submit()

		jv1 = make_journal_entry(
			"Sales Expenses - _TC1",
			"Buildings - _TC1",
			100,
			posting_date=nowdate(),
			cost_center="Main - _TC1",
			save=False,
		)
		jv1.inter_company_journal_entry_reference = jv.name
		jv1.company = "_Test Company 1"
		jv1.voucher_type = "Inter Company Journal Entry"
		jv1.multi_currency = 0
		jv1.insert()
		jv1.submit()

		jv.reload()

		self.assertEqual(jv.inter_company_journal_entry_reference, jv1.name)
		self.assertEqual(jv1.inter_company_journal_entry_reference, jv.name)

		jv.cancel()
		jv1.reload()
		jv.reload()

		self.assertEqual(jv.inter_company_journal_entry_reference, "")
		self.assertEqual(jv1.inter_company_journal_entry_reference, "")

	def test_jv_with_cost_centre(self):
		from erpnext.accounts.doctype.cost_center.test_cost_center import create_cost_center

		cost_center = "_Test Cost Center for BS Account - _TC"
		create_cost_center(cost_center_name="_Test Cost Center for BS Account", company="_Test Company")
		jv = make_journal_entry(
			"_Test Cash - _TC", "_Test Bank - _TC", 100, cost_center=cost_center, save=False
		)
		jv.voucher_type = "Bank Entry"
		jv.multi_currency = 0
		jv.cheque_no = "112233"
		jv.cheque_date = nowdate()
		jv.insert()
		jv.submit()

		self.voucher_no = jv.name

		self.fields = [
			"account",
			"cost_center",
		]

		self.expected_gle = [
			{
				"account": "_Test Bank - _TC",
				"cost_center": cost_center,
			},
			{
				"account": "_Test Cash - _TC",
				"cost_center": cost_center,
			},
		]

		self.check_gl_entries()

	def test_jv_account_and_party_balance_with_cost_centre(self):
		from erpnext.accounts.doctype.cost_center.test_cost_center import create_cost_center
		from erpnext.accounts.utils import get_balance_on

		cost_center = "_Test Cost Center for BS Account - _TC"
		create_cost_center(cost_center_name="_Test Cost Center for BS Account", company="_Test Company")
		jv = make_journal_entry(
			"_Test Cash - _TC", "_Test Bank - _TC", 100, cost_center=cost_center, save=False
		)
		account_balance = get_balance_on(account="_Test Bank - _TC", cost_center=cost_center)
		jv.voucher_type = "Bank Entry"
		jv.multi_currency = 0
		jv.cheque_no = "112233"
		jv.cheque_date = nowdate()
		jv.insert()
		jv.submit()

		expected_account_balance = account_balance - 100
		account_balance = get_balance_on(account="_Test Bank - _TC", cost_center=cost_center)
		self.assertEqual(expected_account_balance, account_balance)

	def test_journal_entry_basic_TC_ACC_049(self):
		# Arrange: Create a simple journal entry
		jv = make_journal_entry("_Test Bank - _TC", "_Test Cash - _TC", 100, save=False)
		jv.voucher_type = "Depreciation Entry"
		jv.insert()

		# Act: Submit the journal entry
		jv.submit()

		# Assert: Verify GL entries
		gl_entries = frappe.db.get_all(
			"GL Entry",
			filters={"voucher_no": jv.name},
			fields=["account", "debit", "credit"],
		)
		self.assertEqual(len(gl_entries), 2)
		self.assertIn({"account": "_Test Bank - _TC", "debit": 100, "credit": 0}, gl_entries)
		self.assertIn({"account": "_Test Cash - _TC", "debit": 0, "credit": 100}, gl_entries)

		# Cleanup: Cancel the journal entry
		jv.cancel()

	def test_journal_entry_credit_note_TC_ACC_051(self):
		# Arrange: Create a Journal Entry with type 'Credit Note'
		jv = make_journal_entry(
			"_Test Receivable - _TC", 
			"_Test Bank - _TC", 
			500, 
			save=False
		)
		jv.voucher_type = "Credit Note"

		# Set Party Type and Party for the receivable account
		jv.accounts[0].party_type = "Customer"
		jv.accounts[0].party = "_Test Customer"

		jv.insert()

		# Act: Submit the Journal Entry
		jv.submit()

		# Assert: Verify GL entries
		gl_entries = frappe.db.get_all(
			"GL Entry",
			filters={"voucher_no": jv.name},
			fields=["account", "debit", "credit"],
		)
		self.assertEqual(len(gl_entries), 2)
		# Correct the expected values for debit and credit
		self.assertIn({"account": "_Test Receivable - _TC", "debit": 500, "credit": 0}, gl_entries)
		self.assertIn({"account": "_Test Bank - _TC", "debit": 0, "credit": 500}, gl_entries)

		# Cleanup: Cancel the Journal Entry
		jv.cancel()


	def test_repost_accounting_entries(self):
		from erpnext.accounts.doctype.cost_center.test_cost_center import create_cost_center

		# Configure Repost Accounting Ledger for JVs
		settings = frappe.get_doc("Repost Accounting Ledger Settings")
		if not [x for x in settings.allowed_types if x.document_type == "Journal Entry"]:
			settings.append("allowed_types", {"document_type": "Journal Entry", "allowed": True})
		settings.save()

		# Create JV with defaut cost center - _Test Cost Center
		jv = make_journal_entry("_Test Cash - _TC", "_Test Bank - _TC", 100, save=False)
		jv.multi_currency = 0
		jv.submit()

		# Check GL entries before reposting
		self.voucher_no = jv.name

		self.fields = [
			"account",
			"debit_in_account_currency",
			"credit_in_account_currency",
			"cost_center",
		]

		self.expected_gle = [
			{
				"account": "_Test Bank - _TC",
				"debit_in_account_currency": 0,
				"credit_in_account_currency": 100,
				"cost_center": "_Test Cost Center - _TC",
			},
			{
				"account": "_Test Cash - _TC",
				"debit_in_account_currency": 100,
				"credit_in_account_currency": 0,
				"cost_center": "_Test Cost Center - _TC",
			},
		]

		self.check_gl_entries()

		# Change cost center for bank account - _Test Cost Center for BS Account
		create_cost_center(cost_center_name="_Test Cost Center for BS Account", company="_Test Company")
		jv.accounts[1].cost_center = "_Test Cost Center for BS Account - _TC"
		# Ledger reposted implicitly upon 'Update After Submit'
		jv.save()

		# Check GL entries after reposting
		jv.load_from_db()
		self.expected_gle[0]["cost_center"] = "_Test Cost Center for BS Account - _TC"
		self.check_gl_entries()

	def check_gl_entries(self):
		gl = frappe.qb.DocType("GL Entry")
		query = frappe.qb.from_(gl)
		for field in self.fields:
			query = query.select(gl[field])

		query = query.where(
			(gl.voucher_type == "Journal Entry") & (gl.voucher_no == self.voucher_no) & (gl.is_cancelled == 0)
		).orderby(gl.account)

		gl_entries = query.run(as_dict=True)
		for i in range(len(self.expected_gle)):
			for field in self.fields:
				self.assertEqual(self.expected_gle[i][field], gl_entries[i][field])

	def test_negative_debit_and_credit_with_same_account_head(self):
		from erpnext.accounts.general_ledger import process_gl_map

		# Create JV with defaut cost center - _Test Cost Center
		frappe.db.set_single_value("Accounts Settings", "merge_similar_account_heads", 0)

		jv = make_journal_entry("_Test Bank - _TC", "_Test Bank - _TC", 100 * -1, save=True)
		jv.append(
			"accounts",
			{
				"account": "_Test Cash - _TC",
				"debit": 100 * -1,
				"credit": 100 * -1,
				"debit_in_account_currency": 100 * -1,
				"credit_in_account_currency": 100 * -1,
				"exchange_rate": 1,
			},
		)
		jv.flags.ignore_validate = True
		jv.save()

		self.assertEqual(len(jv.accounts), 3)

		gl_map = jv.build_gl_map()

		for row in gl_map:
			if row.account == "_Test Cash - _TC":
				self.assertEqual(row.debit_in_account_currency, 100 * -1)
				self.assertEqual(row.credit_in_account_currency, 100 * -1)

		gl_map = process_gl_map(gl_map, False)

		for row in gl_map:
			if row.account == "_Test Cash - _TC":
				self.assertEqual(row.debit_in_account_currency, 100)
				self.assertEqual(row.credit_in_account_currency, 100)
	
	def test_toggle_debit_credit_if_negative(self):
		from erpnext.accounts.general_ledger import process_gl_map
		# Create JV with defaut cost center - _Test Cost Center
		frappe.db.set_single_value("Accounts Settings", "merge_similar_account_heads", 0)
		jv = frappe.new_doc("Journal Entry")
		jv.posting_date = nowdate()
		jv.company = "_Test Company"
		jv.user_remark = "test"
		jv.extend(
			"accounts",
			[
				{
					"account": "_Test Cash - _TC",
					"debit": 100 * -1,
					"debit_in_account_currency": 100 * -1,
					"exchange_rate": 1,
				},
				{
					"account": "_Test Bank - _TC",
					"credit": 100 * -1,
					"credit_in_account_currency": 100 * -1,
					"exchange_rate": 1,
				},
			],
		)
		jv.flags.ignore_validate = True
		jv.save()
		self.assertEqual(len(jv.accounts), 2)
		gl_map = jv.build_gl_map()
		for row in gl_map:
			if row.account == "_Test Cash - _TC":
				self.assertEqual(row.debit, 100 * -1)
				self.assertEqual(row.debit_in_account_currency, 100 * -1)
				self.assertEqual(row.debit_in_transaction_currency, 100 * -1)
		gl_map = process_gl_map(gl_map, False)
		for row in gl_map:
			if row.account == "_Test Cash - _TC":
				self.assertEqual(row.credit, 100)
				self.assertEqual(row.credit_in_account_currency, 100)
				self.assertEqual(row.credit_in_transaction_currency, 100)

	def test_transaction_exchange_rate_on_journals(self):
		jv = make_journal_entry("_Test Bank - _TC", "_Test Receivable USD - _TC", 100, save=False)
		jv.accounts[0].update({"debit_in_account_currency": 8500, "exchange_rate": 1})
		jv.accounts[1].update({"party_type": "Customer", "party": "_Test Customer USD", "exchange_rate": 85})
		jv.submit()
		actual = frappe.db.get_all(
			"GL Entry",
			filters={"voucher_no": jv.name, "is_cancelled": 0},
			fields=["account", "transaction_exchange_rate"],
			order_by="account",
		)
		expected = [
			{"account": "_Test Bank - _TC", "transaction_exchange_rate": 85.0},
			{"account": "_Test Receivable USD - _TC", "transaction_exchange_rate": 85.0},
		]
		self.assertEqual(expected, actual)
	
	def test_select_tds_payable_and_creditors_account_TC_ACC_024(self):
		from erpnext.accounts.doctype.payment_entry.test_payment_entry import create_records

		create_records('_Test Supplier TDS')

		supplier = frappe.get_doc("Supplier", "_Test Supplier TDS")
		account = frappe.get_doc("Account", "_Test TDS Payable - _TC")
		
		if supplier and account:
			jv=frappe.new_doc("Journal Entry")
			jv.posting_date = nowdate()
			jv.company = "_Test Company"
			jv.set('accounts',
				[ 
     				{
						"account": account.name,
						"debit_in_account_currency": 0,
						"credit_in_account_currency": 1000
					},
					{
						"account": 'Creditors - _TC',
						"party_type": "Supplier",
						"party": supplier.name,
						"debit_in_account_currency": 1000,
						"credit_in_account_currency": 0
					},
     			]
			)
			jv.save()
			jv.submit()
			self.voucher_no = jv.name

			self.fields = [
				"account",
				"debit_in_account_currency",
				"credit_in_account_currency",
				"cost_center",
			]

			self.expected_gle = [
				{
					"account": 'Creditors - _TC',
					"debit_in_account_currency": 1000,
					"credit_in_account_currency": 0,
					"cost_center": "Main - _TC",
				},
				{
					"account": account.name,
					"debit_in_account_currency": 0,
					"credit_in_account_currency": 1000,
					"cost_center": "Main - _TC",
				},
			]

			self.check_gl_entries()

	def test_round_off_entry_TC_ACC_050(self):
		# Set up round-off account and cost center
		frappe.db.set_value("Company", "_Test Company", "round_off_account", "_Test Write Off - _TC")
		frappe.db.set_value("Company", "_Test Company", "round_off_cost_center", "_Test Cost Center - _TC")

		# Create a journal entry
		jv = make_journal_entry(
			"_Test Account Cost for Goods Sold - _TC",
			"_Test Bank - _TC",
			100,
			"_Test Cost Center - _TC",
			submit=False,
		)
		jv.get("accounts")[0].debit = 100.01
		jv.flags.ignore_validate = True
		jv.submit()

		# Fetch round-off GL Entry
		round_off_entry = frappe.db.sql(
			"""select debit, credit, account, cost_center 
			from `tabGL Entry`
			where voucher_type='Journal Entry' and voucher_no = %s
			and account='_Test Write Off - _TC' and cost_center='_Test Cost Center - _TC'""",
			jv.name,
			as_dict=True,
		)
		self.assertTrue(round_off_entry, "Round-off entry not found.")

		# Validate the round-off amount
		entry = round_off_entry[0]
		self.assertEqual(entry["debit"], 0, "Round-off debit is incorrect.")
		self.assertEqual(entry["credit"], 0.01, "Round-off credit is incorrect.")

		# Validate the debit and credit accounts for the main journal entry
		debit_account = frappe.db.get_value(
			"GL Entry", 
			{"voucher_no": jv.name, "voucher_type": "Journal Entry", "debit": 100.01}, 
			"account"
		)
		credit_account = frappe.db.get_value(
			"GL Entry", 
			{"voucher_no": jv.name, "voucher_type": "Journal Entry", "credit": 100}, 
			"account"
		)

		self.assertEqual(debit_account, "_Test Account Cost for Goods Sold - _TC", "Debit account is incorrect.")
		self.assertEqual(credit_account, "_Test Bank - _TC", "Credit account is incorrect.")

	def test_debit_note_entry_TC_ACC_052(self):
		# Set up parameters
		party_type = "Customer"
		party = "_Test Customer"
		account1 = "Debtors - _TC"  # Debit Account
		account2 = "Cash - _TC"  # Credit Account
		amount = 1000.0


		# Create the Journal Entry for Debit Note
		jv = make_journal_entry(
			account1=account1,
			account2=account2,
			amount=amount,
			# cost_center=cost_center,
			save=False,
			submit=False
		)

		# Update party details for GL entries
		for account in jv.accounts:
			if account.account == "Debtors - _TC":
				account.party_type = party_type
				account.party = party
		jv.save()
		jv.submit()

		# Fetch the GL Entries for the created JV
		gl_entries = frappe.db.sql(
			"""SELECT account, debit, credit, party_type, party
				FROM `tabGL Entry`
				WHERE voucher_no = %s AND voucher_type = 'Journal Entry'""",
			jv.name,
			as_dict=True
		)

		# Assertions
		self.assertEqual(len(gl_entries), 2, "Incorrect number of GL Entries created.")	
	
	def test_contra_entry_TC_ACC_053(self):
		# Set up input parameters
		entry_type = "Contra Entry"
		debit_account = "_Test Bank - _TC"
		credit_account = "_Test Cash - _TC"
		amount = 50000.0

		# Create the Journal Entry using the existing function
		jv = make_journal_entry(
			account1=debit_account,
			account2=credit_account,
			amount=amount,
			save=False,
			submit=False,
		)

		# Set the entry type and save the journal entry
		jv.entry_type = entry_type
		jv.save()
		jv.submit()

		# Fetch GL Entries to validate the transaction
		gl_entries = frappe.db.sql(
			"""SELECT account, debit, credit FROM `tabGL Entry`
				WHERE voucher_type='Journal Entry' AND voucher_no=%s
				ORDER BY account""",
			jv.name,
			as_dict=True,
		)

		# Expected GL entries
		expected_gl_entries = [
			{"account": debit_account, "debit": amount, "credit": 0},
			{"account": credit_account, "debit": 0, "credit": amount},
		]

		# Assertions
		self.assertEqual(len(gl_entries), 2, "Incorrect number of GL entries created.")
		for entry, expected in zip(gl_entries, expected_gl_entries):
			self.assertEqual(entry["account"], expected["account"], "Account mismatch in GL Entry.")
			self.assertEqual(entry["debit"], expected["debit"], f"Debit mismatch for {entry['account']}.")
			self.assertEqual(entry["credit"], expected["credit"], f"Credit mismatch for {entry['account']}.")

	def test_payment_of_gst_tds_TC_ACC_054(self):
		# Set up input parameters
		entry_type = "Journal Entry"
		credit_account = "_Test Bank - _TC"
		amount = 20000.0
		tax_accounts = frappe.get_all(
			"Account",
			filters={"company":"_Test Company","account_type": "Tax", "parent_account": ["like", "%Assets%"]},
			fields=["name"]
		)

		# Identify SGST and CGST accounts based on their name
		debit_account = None
		debit_account_cgst = None

		for account in tax_accounts:
			if "IGST" in account["name"]:
				debit_account = account["name"]

		# Ensure both SGST and CGST accounts are found
		if not debit_account:
			self.fail(f"Could not find IGST account: {tax_accounts}")
		# Create the Journal Entry using the existing function
		jv = make_journal_entry(
			account1=debit_account,
			account2=credit_account,
			amount=amount,
			save=False,
			submit=False,
		)

		# Set the entry type and save the journal entry
		jv.entry_type = entry_type
		jv.save()
		jv.submit()

		# Fetch GL Entries to validate the transaction
		gl_entries = frappe.db.sql(
			"""SELECT account, debit, credit FROM `tabGL Entry`
				WHERE voucher_type='Journal Entry' AND voucher_no=%s
				ORDER BY account""",
			jv.name,
			as_dict=True,
		)

		# Expected GL entries
		expected_gl_entries = [
			{"account": debit_account, "debit": amount, "credit": 0},
			{"account": credit_account, "debit": 0, "credit": amount},
		]

		# Assertions
		self.assertEqual(len(gl_entries), 2, "Incorrect number of GL entries created.")
		for entry, expected in zip(gl_entries, expected_gl_entries):
			self.assertEqual(entry["account"], expected["account"], "Account mismatch in GL Entry.")
			self.assertEqual(entry["debit"], expected["debit"], f"Debit mismatch for {entry['account']}.")
			self.assertEqual(entry["credit"], expected["credit"], f"Credit mismatch for {entry['account']}.")

	def test_deferred_expense_entry_TC_ACC_055(self):
		# Set up input parameters
		entry_type = "Deferred Expense"
		debit_account = "_Test Accumulated Depreciations - _TC"
		credit_account = "Creditors - _TC"
		amount = 30000.0

		# Create the Journal Entry using the existing function
		jv = make_journal_entry(
			account1=debit_account,
			account2=credit_account,
			amount=amount,
			save=False,
			submit=False,
		)
		for account in jv.accounts:
			if account.account == "Creditors - _TC":
				account.party_type = "Supplier"
				account.party = "_Test Supplier"
		# Set the entry type and save the journal entry
		jv.entry_type = entry_type
		jv.save().submit()

		# Fetch GL Entries to validate the transaction
		gl_entries = frappe.db.sql(
			"""SELECT account, debit, credit FROM `tabGL Entry`
				WHERE voucher_type='Journal Entry' AND voucher_no=%s
				ORDER BY account""",
			jv.name,
			as_dict=True,
		)
		print("Here we are printing the GL Entries ",gl_entries )
		# Expected GL entries
		expected_gl_entries = [
			{"account": credit_account, "debit": 0, "credit": amount},
			{"account": debit_account, "debit": amount, "credit": 0}
		]

		# Assertions
		self.assertEqual(len(gl_entries), 2, "Incorrect number of GL entries created.")
		for entry, expected in zip(gl_entries, expected_gl_entries):
			self.assertEqual(entry["account"], expected["account"], "Account mismatch in GL Entry.")
			self.assertEqual(entry["debit"], expected["debit"], f"Debit mismatch for {entry['account']}.")
			self.assertEqual(entry["credit"], expected["credit"], f"Credit mismatch for {entry['account']}.")

	def test_deferred_expense_entry_TC_ACC_056(self):
		# Set up input parameters
		entry_type = "Deferred Expense"
		debit_account = "Write Off - _TC"
		credit_account = "_Test Accumulated Depreciations - _TC"
		amount = 30000.0

		# Create the Journal Entry using the existing function
		jv = make_journal_entry(
			account1=debit_account,
			account2=credit_account,
			amount=amount,
			save=False,
			submit=False,
		)
		# Set the entry type and save the journal entry
		jv.entry_type = entry_type
		jv.save().submit()

		# Fetch GL Entries to validate the transaction
		gl_entries = frappe.db.sql(
			"""SELECT account, debit, credit FROM `tabGL Entry`
				WHERE voucher_type='Journal Entry' AND voucher_no=%s
				ORDER BY account""",
			jv.name,
			as_dict=True,
		)
		# Expected GL entries
		expected_gl_entries = [
			{"account": credit_account, "debit": 0, "credit": amount},
			{"account": debit_account, "debit": amount, "credit": 0}
		]

		# Assertions
		self.assertEqual(len(gl_entries), 2, "Incorrect number of GL entries created.")
		for entry, expected in zip(gl_entries, expected_gl_entries):
			self.assertEqual(entry["account"], expected["account"], "Account mismatch in GL Entry.")
			self.assertEqual(entry["debit"], expected["debit"], f"Debit mismatch for {entry['account']}.")
			self.assertEqual(entry["credit"], expected["credit"], f"Credit mismatch for {entry['account']}.")
	
	def test_deferred_revenue_entry_TC_ACC_057(self):
		# Set up input parameters
		entry_type = "Deferred Revenue"
		debit_account = "Debtors - _TC"
		credit_account = "Creditors - _TC"
		amount = 30000.0

		# Create the Journal Entry using the existing function
		jv = make_journal_entry(
			account1=debit_account,
			account2=credit_account,
			amount=amount,
			save=False,
			submit=False,
		)
		for account in jv.accounts:
			if account.account == "Creditors - _TC":
				account.party_type = "Supplier"
				account.party = "_Test Supplier"

			elif account.account == "Debtors - _TC":
				account.party_type = "Customer"
				account.party = "_Test Customer"
		# Set the entry type and save the journal entry
		jv.entry_type = entry_type
		jv.save().submit()

		# Fetch GL Entries to validate the transaction
		gl_entries = frappe.db.sql(
			"""SELECT account, debit, credit FROM `tabGL Entry`
				WHERE voucher_type='Journal Entry' AND voucher_no=%s
				ORDER BY account""",
			jv.name,
			as_dict=True,
		)
		# Expected GL entries
		expected_gl_entries = [
			{"account": credit_account, "debit": 0, "credit": amount},
			{"account": debit_account, "debit": amount, "credit": 0}
		]

		# Assertions
		self.assertEqual(len(gl_entries), 2, "Incorrect number of GL entries created.")
		for entry, expected in zip(gl_entries, expected_gl_entries):
			self.assertEqual(entry["account"], expected["account"], "Account mismatch in GL Entry.")
			self.assertEqual(entry["debit"], expected["debit"], f"Debit mismatch for {entry['account']}.")
			self.assertEqual(entry["credit"], expected["credit"], f"Credit mismatch for {entry['account']}.")

	def test_deferred_revenue_entry_TC_ACC_058(self):
		# Set up input parameters
		entry_type = "Deferred Revenue"
		debit_account = "Creditors - _TC"
		credit_account = "Sales - _TC"
		amount = 30000.0

		# Create the Journal Entry using the existing function
		jv = make_journal_entry(
			account1=debit_account,
			account2=credit_account,
			amount=amount,
			save=False,
			submit=False,
		)
		for account in jv.accounts:
			if account.account == "Creditors - _TC":
				account.party_type = "Supplier"
				account.party = "_Test Supplier"
		# Set the entry type and save the journal entry
		jv.entry_type = entry_type
		jv.save().submit()

		# Fetch GL Entries to validate the transaction
		gl_entries = frappe.db.sql(
			"""SELECT account, debit, credit FROM `tabGL Entry`
				WHERE voucher_type='Journal Entry' AND voucher_no=%s
				ORDER BY account""",
			jv.name,
			as_dict=True,
		)
		# Expected GL entries
		expected_gl_entries = [
			{"account": debit_account, "debit": amount, "credit": 0},
			{"account": credit_account, "debit": 0, "credit": amount}

		]

		# Assertions
		self.assertEqual(len(gl_entries), 2, "Incorrect number of GL entries created.")
		for entry, expected in zip(gl_entries, expected_gl_entries):
			self.assertEqual(entry["account"], expected["account"], "Account mismatch in GL Entry.")
			self.assertEqual(entry["debit"], expected["debit"], f"Debit mismatch for {entry['account']}.")
			self.assertEqual(entry["credit"], expected["credit"], f"Credit mismatch for {entry['account']}.")

	def test_reversal_of_itc_TC_ACC_059(self):
		# Set up input parameters
		entry_type = "Reversal of ITC"
		credit_account = "Creditors - _TC"
		amount_sgst = 5000.0
		amount_cgst = 5000.0

		# Fetch Tax Accounts dynamically
		tax_accounts = frappe.get_all(
			"Account",
			filters={"company":"_Test Company","account_type": "Tax", "parent_account": ["like", "%Assets%"]},
			fields=["name"]
		)

		# Identify SGST and CGST accounts based on their name
		debit_account_sgst = None
		debit_account_cgst = None

		for account in tax_accounts:
			if "SGST" in account["name"]:
				debit_account_sgst = account["name"]
			elif "CGST" in account["name"]:
				debit_account_cgst = account["name"]

		# Ensure both SGST and CGST accounts are found
		if not debit_account_sgst or not debit_account_cgst:
			self.fail(f"Could not find SGST or CGST accounts. Found: {tax_accounts}")

		# Create the Journal Entry
		jv = frappe.new_doc("Journal Entry")
		jv.posting_date = nowdate()
		jv.company = "_Test Company"
		jv.entry_type = entry_type
		jv.user_remark = "Reversal of ITC Test Case"

		# Add accounts to the Journal Entry
		jv.append("accounts", {
			"account": debit_account_sgst,
			"debit_in_account_currency": amount_sgst,
			"credit_in_account_currency": 0,
			"cost_center": "_Test Cost Center - _TC"
		})

		jv.append("accounts", {
			"account": debit_account_cgst,
			"debit_in_account_currency": amount_cgst,
			"credit_in_account_currency": 0,
			"cost_center": "_Test Cost Center - _TC"
		})

		jv.append("accounts", {
			"account": credit_account,
			"debit_in_account_currency": 0,
			"credit_in_account_currency": amount_sgst + amount_cgst,
			"cost_center": "_Test Cost Center - _TC",
			"party_type": "Supplier",
			"party": "_Test Supplier"
		})

		# Save and submit the Journal Entry
		jv.insert()
		jv.submit()

		# Fetch GL Entries to validate the transaction
		gl_entries = frappe.db.sql(
			"""SELECT account, debit, credit FROM `tabGL Entry`
				WHERE voucher_type='Journal Entry' AND voucher_no=%s
				ORDER BY account""",
			jv.name,
			as_dict=True,
		)

		# Expected GL entries
		expected_gl_entries = [
			{"account": credit_account, "debit": 0, "credit": amount_sgst + amount_cgst},
			{"account": debit_account_cgst, "debit": amount_cgst, "credit": 0},
			{"account": debit_account_sgst, "debit": amount_sgst, "credit": 0},
		]

		# Assertions
		self.assertEqual(len(gl_entries), 3, "Incorrect number of GL entries created.")
		for entry, expected in zip(gl_entries, expected_gl_entries):
			self.assertEqual(entry["account"], expected["account"], f"Account mismatch in GL Entry: {entry['account']}.")
			self.assertEqual(entry["debit"], expected["debit"], f"Debit mismatch for {entry['account']}.")
			self.assertEqual(entry["credit"], expected["credit"], f"Credit mismatch for {entry['account']}.")

	def test_exchange_gain_or_loss_TC_ACC_060(self):
		# Set up input parameters
		entry_type = "Exchange Gain or Loss"
		debit_account = "Exchange Gain/Loss - _TC"
		credit_account = "Debtors - _TC"
		party_type = "Customer"
		party = "_Test Customer"
		new_exchange_rate = 75.0
		amount = 1000.0

		# Create the Journal Entry using the make_journal_entry method
		jv = make_journal_entry(
			account1=debit_account,
			account2=credit_account,
			amount=amount,
			save=False,
			submit=False
		)

		for account in jv.accounts:
			if account.account == credit_account:
				account.party_type = party_type
				account.party = party
				account.exchange_rate = new_exchange_rate

		# Set the entry type and save the journal entry
		jv.entry_type = entry_type
		jv.save().submit()

		# Fetch GL Entries to validate the transaction
		gl_entries = frappe.db.sql(
			"""SELECT account, debit, credit FROM `tabGL Entry`
				WHERE voucher_type='Journal Entry' AND voucher_no=%s
				ORDER BY account""",
			jv.name,
			as_dict=True,
		)

		# Expected GL entries
		expected_gl_entries = [
			{"account": credit_account, "debit": 0, "credit": amount},
			{"account": debit_account, "debit": amount, "credit": 0},
		]

		# Assertions
		self.assertEqual(len(gl_entries), 2, "Incorrect number of GL entries created.")
		for entry, expected in zip(gl_entries, expected_gl_entries):
			self.assertEqual(entry["account"], expected["account"], f"Account mismatch in GL Entry: {entry['account']}.")
			self.assertEqual(entry["debit"], expected["debit"], f"Debit mismatch for {entry['account']}.")
			self.assertEqual(entry["credit"], expected["credit"], f"Credit mismatch for {entry['account']}.")

	def test_exchange_rate_revaluation_TC_ACC_061(self):
		# Set up input parameters
		entry_type = "Exchange Rate Revaluation"
		debit_account = "Creditors - _TC"
		credit_account = "Exchange Gain/Loss - _TC"
		party_type = "Supplier"
		party = "_Test Supplier"
		new_exchange_rate = 80.0
		amount = 2000.0

		# Create the Journal Entry
		jv = make_journal_entry(
			account1=debit_account,
			account2=credit_account,
			amount=amount,
			save=False,
			submit=False
		)

		for account in jv.accounts:
			if account.account == debit_account:
				account.party_type = party_type
				account.party = party
				account.exchange_rate = new_exchange_rate

		# Set the entry type and save the journal entry
		jv.entry_type = entry_type
		jv.save().submit()

		# Fetch GL Entries to validate the transaction
		gl_entries = frappe.db.sql(
			"""SELECT account, debit, credit FROM `tabGL Entry`
				WHERE voucher_type='Journal Entry' AND voucher_no=%s
				ORDER BY account""",
			jv.name,
			as_dict=True,
		)

		# Expected GL entries
		expected_gl_entries = [
			{"account": debit_account, "debit": amount, "credit": 0},
			{"account": credit_account, "debit": 0, "credit": amount},
		]

		# Assertions
		self.assertEqual(len(gl_entries), 2, "Incorrect number of GL entries created.")
		for entry, expected in zip(gl_entries, expected_gl_entries):
			self.assertEqual(entry["account"], expected["account"], f"Account mismatch in GL Entry: {entry['account']}.")
			self.assertEqual(entry["debit"], expected["debit"], f"Debit mismatch for {entry['account']}.")
			self.assertEqual(entry["credit"], expected["credit"], f"Credit mismatch for {entry['account']}.")
  
	def test_create_jv_for_cash_enrty_TC_ACC_082(self):
		jv=make_journal_entry(
			account1="Cash - _TC",
			account2="_Test Payable - _TC",
			amount=1000.0,
			exchange_rate=0,
			save=False,
			submit=False
		)
		for account in jv.accounts:
			if account.account=="_Test Payable - _TC":
				account.party_type = "Supplier"
				account.party = "_Test Supplier"
		jv.save().submit()
		self.voucher_no = jv.name
		self.fields = [
			"account",
			"account_currency",
			"debit",
			"debit_in_account_currency",
			"credit",
			"credit_in_account_currency",
		]

		self.expected_gle = [
			{
				"account": "Cash - _TC",
				"account_currency": "INR",
				"debit": 1000,
				"debit_in_account_currency": 1000,
				"credit": 0 ,
				"credit_in_account_currency": 0,
			},
			{
				"account": "_Test Payable - _TC",
				"account_currency": "INR",
				"debit": 0,
				"debit_in_account_currency": 0,
				"credit": 1000,
				"credit_in_account_currency": 1000,
			},
		]
		self.check_gl_entries()
  
	def test_create_jv_for_bank_enrty_TC_ACC_083(self):
		jv=make_journal_entry(
			account1="_Test Bank - _TC",
			account2="_Test Receivable - _TC",
			amount=1000.0,
			exchange_rate=0,
			save=False,
			submit=False
		)
		jv.voucher_type="Bank Entry"
		jv.cheque_no="112233"
		jv.cheque_date=nowdate()
		for account in jv.accounts:
			if account.account=="_Test Receivable - _TC":
				account.party_type = "Customer"
				account.party = "_Test Customer"
		jv.save().submit()
		self.voucher_no = jv.name
		self.fields = [
			"account",
			"account_currency",
			"debit",
			"debit_in_account_currency",
			"credit",
			"credit_in_account_currency",
		]

		self.expected_gle = [
			{
				"account": "_Test Bank - _TC",
				"account_currency": "INR",
				"debit": 1000,
				"debit_in_account_currency": 1000,
				"credit": 0 ,
				"credit_in_account_currency": 0,
			},
			{
				"account": "_Test Receivable - _TC",
				"account_currency": "INR",
				"debit": 0,
				"debit_in_account_currency": 0,
				"credit": 1000,
				"credit_in_account_currency": 1000,
			},
		]
		self.check_gl_entries()
	def test_create_jv_with_jv_template_TC_ACC_084(self):
		
		if not frappe.db.exists("Journal Entry Template", "_Test Template"):
			template = frappe.new_doc("Journal Entry Template")
			template.template_title="_Test Template"
			template.company="_Test Company"
			template.naming_series="ACC-JV-.YYYY.-"
			template.append("accounts",{
				"account":"Cash - _TC",
			})
			template.insert()
		template=frappe.get_doc("Journal Entry Template","_Test Template")
		jv = frappe.get_doc({
			"doctype": "Journal Entry",
			"company": "_Test Company",
			"posting_date": frappe.utils.nowdate(),
			"from_template": template.name,
			"accounts": [
				{
					"account":template.accounts[0].account,
					"account_currency": "INR",
					"debit": 10000,
					"debit_in_account_currency": 10000,
					"credit": 0,
					"credit_in_account_currency": 0,
				}
			],
		}).insert()
		jv.append("accounts", {
			"account": "_Test Payable - _TC",
			"account_currency": "INR",
			"party_type": "Supplier",
			"party": "_Test Supplier",
			"debit": 0,
			"debit_in_account_currency": 0,
			"credit": 10000,
			"credit_in_account_currency": 10000,
		})
		jv.save().submit()	

		self.voucher_no = jv.name
		self.fields = [
			"account",
			"account_currency",
			"debit",
			"debit_in_account_currency",
			"credit",
			"credit_in_account_currency",
		]

		self.expected_gle = [
			{
				"account": "Cash - _TC",
				"account_currency": "INR",
				"debit": 10000,
				"debit_in_account_currency": 10000,
				"credit": 0 ,
				"credit_in_account_currency": 0,
			},
			{
				"account": "_Test Payable - _TC",
				"account_currency": "INR",
				"debit": 0,
				"debit_in_account_currency": 0,
				"credit": 10000,
				"credit_in_account_currency": 10000,
			}
		]

		self.check_gl_entries()
  
	def test_opening_entry_TC_ACC_116(self):
		from erpnext.accounts.doctype.payment_entry.test_payment_entry import create_records
		create_records("_Test Supplier")
		jv = frappe.get_doc({
			"doctype": "Journal Entry",
			"voucher_type": "Opening Entry",
			"company": "_Test Company",
			"posting_date": frappe.utils.nowdate(),
			"accounts":[
				{
					"account":"_Test Payable - _TC",
					"party_type": "Supplier",
					"party": "_Test Supplier",
					"debit_in_account_currency":1000,
				},
				{
					"account": "_Test Creditors - _TC",
					"credit_in_account_currency":1000,
					"party_type": "Supplier",
					"party": "_Test Supplier"
				},
				{
					"account":"Debtors - _TC",
					"party_type":"Customer",
					"party": "_Test Customer",
					"debit_in_account_currency":1000,
				},
				{
					"account":"_Test Receivable - _TC",
					"party_type":"Customer",
					"party": "_Test Customer",
					"credit_in_account_currency":1000,
				},
				{
					"account":"Cash - _TC",
					"debit_in_account_currency":2000
				},
				{
					"account":"Temporary Opening - _TC",
					"credit_in_account_currency":2000
				}
			]
		}).insert()
		jv.submit()
		self.voucher_no = jv.name
		self.fields = [
			"account",
			"account_currency",
			"debit",
			"debit_in_account_currency",
			"credit",
			"credit_in_account_currency",
		]

		self.expected_gle = [
				{
					'account': 'Cash - _TC',
					'account_currency': 'INR',
					'debit': 2000.0,
					'debit_in_account_currency': 2000.0,
					'credit': 0.0,
					'credit_in_account_currency': 0.0
				},
				{
					'account': 'Debtors - _TC',
					'account_currency': 'INR',
					'debit': 1000.0,
					'debit_in_account_currency': 1000.0,
					'credit': 0.0,
					'credit_in_account_currency': 0.0
				},
				{
					'account': 'Temporary Opening - _TC',
					'account_currency': 'INR',
					'debit': 0.0,
					'debit_in_account_currency': 0.0,
					'credit': 2000.0,
					'credit_in_account_currency': 2000.0
				},
				{
					'account': '_Test Creditors - _TC',
					'account_currency': 'INR',
					'debit': 0.0,
					'debit_in_account_currency': 0.0,
					'credit': 1000.0,
					'credit_in_account_currency': 1000.0
				},
				{
					'account': '_Test Payable - _TC',
					'account_currency': 'INR',
					'debit': 1000.0,
					'debit_in_account_currency': 1000.0,
					'credit': 0.0,
					'credit_in_account_currency': 0.0
				},
				{
					'account': '_Test Receivable - _TC',
					'account_currency': 'INR',
					'debit': 0.0,
					'debit_in_account_currency': 0.0,
					'credit': 1000.0,
					'credit_in_account_currency': 1000.0
				}
			]

		self.check_gl_entries()
  
	def test_reverse_journal_entry_TC_ACC_107(self):
		from erpnext.accounts.doctype.journal_entry.journal_entry import make_reverse_journal_entry
		jv = make_journal_entry(
			account1="Cost of Goods Sold - _TC",
			account2="Cash - _TC",
			amount=10000.0,
			save=False,
			submit=False
		)
		jv.voucher_type = "Journal Entry"
		jv.save().submit()
		self.voucher_no = jv.name
		self.fields = [
			"account",
			"account_currency",
			"debit",
			"debit_in_account_currency",
			"credit",
			"credit_in_account_currency",
		]
		self.expected_gle = [
			{
				'account': 'Cash - _TC',
				'account_currency': 'INR',
				'debit': 0.0,
				'debit_in_account_currency': 0.0,
				'credit': 10000.0,
				'credit_in_account_currency': 10000.0
			},
			{
				'account': 'Cost of Goods Sold - _TC',
				'account_currency': 'INR',
				'debit': 10000.0,
				'debit_in_account_currency': 10000.0,
				'credit': 0.0,
				'credit_in_account_currency': 0.0
			}
		]

		self.check_gl_entries()
		
		_jv = make_reverse_journal_entry(jv.name)
		_jv.posting_date = nowdate()
		_jv.save().submit()
		self.voucher_no = _jv.name
		self.fields = [
			"account",
			"account_currency",
			"debit",
			"debit_in_account_currency",
			"credit",
			"credit_in_account_currency",
		]
		self.expected_gle=[
			{
				'account': 'Cash - _TC',
				'account_currency': 'INR',
				'debit': 10000.0,
				'debit_in_account_currency': 10000.0,
				'credit': 0.0,
				'credit_in_account_currency': 0.0
			},
			{
				'account': 'Cost of Goods Sold - _TC',
				'account_currency': 'INR',
				'debit': 0.0,
				'debit_in_account_currency': 0.0,
				'credit': 10000.0,
				'credit_in_account_currency': 10000.0
			}
		]

		self.check_gl_entries()
  
	def test_make_differnce_function_TC_ACC_108(self):
     
		jv = frappe.get_doc({
			"doctype": "Journal Entry",
			"company": "_Test Company",
			"posting_date": nowdate(),
			"accounts": [
				{
					"account":"Cash - _TC",
					"cost_center":"Main - _TC",
					"debit_in_account_currency":1000,
					"credit_in_account_currency":0
				},
			]
		}).insert()
		jv.get_balance()
		jv.accounts[1].account="Cost of Goods Sold - _TC"
		jv.accounts[1].cost_center="Main - _TC"
		jv.save()
		self.assertEqual(jv.accounts[0].debit_in_account_currency, jv.accounts[1].credit_in_account_currency)
		
def make_journal_entry(
	account1,
	account2,
	amount,
	cost_center=None,
	posting_date=None,
	exchange_rate=1,
	save=True,
	submit=False,
	project=None,
):
	if not cost_center:
		cost_center = "_Test Cost Center - _TC"

	jv = frappe.new_doc("Journal Entry")
	jv.posting_date = posting_date or nowdate()
	jv.company = "_Test Company"
	jv.user_remark = "test"
	jv.multi_currency = 1
	jv.set(
		"accounts",
		[
			{
				"account": account1,
				"cost_center": cost_center,
				"project": project,
				"debit_in_account_currency": amount if amount > 0 else 0,
				"credit_in_account_currency": abs(amount) if amount < 0 else 0,
				"exchange_rate": exchange_rate,
			},
			{
				"account": account2,
				"cost_center": cost_center,
				"project": project,
				"credit_in_account_currency": amount if amount > 0 else 0,
				"debit_in_account_currency": abs(amount) if amount < 0 else 0,
				"exchange_rate": exchange_rate,
			},
		],
	)
	if save or submit:
		jv.insert()

		if submit:
			jv.submit()

	return jv


test_records = frappe.get_test_records("Journal Entry")
