# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestOpenItemReconciliation(FrappeTestCase):
	def tearDown(self):
		super().tearDown()
		frappe.db.rollback()
  
	def test_fetch_unreconciled_gl_entries_with_real_gl_TC_SCK_438(self):
		from erpnext.accounts.doctype.payment_entry.test_payment_entry import (
			create_company,
			create_customer,
			create_sales_invoice,
			create_payment_entry,
		)
		from erpnext.accounts.doctype.purchase_invoice.test_purchase_invoice import check_gl_entries
		from erpnext.stock.doctype.item.test_item import make_item
		from erpnext.accounts.doctype.cost_center.test_cost_center import create_cost_center
		from erpnext.accounts.doctype.account.test_account import create_account
		from erpnext.stock.doctype.warehouse.test_warehouse import create_warehouse
		# Create mock GL Entries
		company = "_Test Company"
		cost_center = "_Test Cost Center - _TC"
		create_company(company)
		create_customer(name="_Test Customer", currency="INR")
		create_cost_center(cost_center_name="_Test Cost Center", company=company)
		account = create_account(
			account_name="Open Items",
			parent_account="Accounts Receivable - _TC",
			company=company,
			account_currency="INR",
			do_not_save=True
		)
		account.is_open_item = 1
		account.report_type = "Balance Sheet"
		account.save(ignore_permissions=True)
		create_warehouse(warehouse_name="_Test Warehouse", company=company)
		validate_fiscal_year(company)
		item = make_item("_Test Item", {"is_stock_item": 1})
		si = create_sales_invoice(
			customer="_Test Customer",
			company=company,
			item=item.name,
			rate=1000,
			income_account=account.name,
			do_not_submit=True
	
		)
		si.submit()
		pe = create_payment_entry(
			company=company,
			payment_type="Receive",
			party_type="Customer",
			party="_Test Customer",
			paid_from=account.name,
			paid_to="Cash - _TC",
			paid_amount=1000
		)
		pe.save().submit()
		credit_gl = frappe.get_doc({
			"doctype": "GL Entry",
			"company": company,
			"posting_date": si.posting_date,
			"account": account.name,
			"party_type": "Customer",
			"party": "_Test Customer",
			"debit": 0,
			"credit": 1000,
			"debit_in_account_currency": 0,
			"credit_in_account_currency": 1000,
			"voucher_type": "Sales Invoice",
			"voucher_no": si.name,
			"is_cancelled": 0,
			"is_opening": "No",
			"is_reconciled": 0,
			"cost_center": cost_center,
			"unreconciled_amount": 1000,
		})
		credit_gl.insert()
		debit_gl = frappe.get_doc({
			"doctype": "GL Entry",
			"company": company,
			"posting_date": pe.posting_date,
			"account": account.name,
			"party_type": "Customer",
			"party": "_Test Customer",
			"debit": 500,
			"credit": 0,
			"debit_in_account_currency": 500,
			"credit_in_account_currency": 0,
			"voucher_type": "Payment Entry",
			"voucher_no": pe.name,
			"is_cancelled": 0,
			"is_opening": "No",
			"is_reconciled": 0,
			"cost_center": cost_center,
			"unreconciled_amount": 500,
		})
		debit_gl.insert()

		recon = frappe.get_doc({
			"doctype": "Open Item Reconciliation",
			"company": company,
			"account": account.name,
			"party_type": "Customer",
			"party": "_Test Customer",
			"cost_center": cost_center
		})

		recon.fetch_unreconciled_gl_entries()
		self.assertEqual(recon.credit_amount[1].outstanding_amount, 1000)
		self.assertEqual(recon.credit_amount[1].voucher_type, "Sales Invoice")
		self.assertEqual(recon.credit_amount[1].voucher_no, si.name)

		self.assertEqual(len(recon.debit_amount), 1)
		self.assertEqual(recon.debit_amount[0].outstanding_amount, 500)
		self.assertEqual(recon.debit_amount[0].voucher_type, "Payment Entry")
		self.assertEqual(recon.debit_amount[0].voucher_no, pe.name)
		
	def test_remove_current_glr_row_TC_SCK_439(self):
		from erpnext.accounts.doctype.payment_entry.test_payment_entry import (
			create_company,
			create_customer,
			create_sales_invoice,
			create_payment_entry,
		)
		from erpnext.stock.doctype.item.test_item import make_item
		from erpnext.accounts.doctype.cost_center.test_cost_center import create_cost_center
		from erpnext.accounts.doctype.account.test_account import create_account
		from erpnext.stock.doctype.warehouse.test_warehouse import create_warehouse

		company = "_Test Company"
		create_company(company)
		create_customer(name="_Test Customer", currency="INR")
		create_cost_center(cost_center_name="_Test Cost Center", company=company)
		account = create_account(
			account_name="Open Items",
			parent_account="Accounts Receivable - _TC",
			company=company,
			account_currency="INR",
			do_not_save=True
		)
		account.is_open_item = 1
		account.report_type = "Balance Sheet"
		account.save(ignore_permissions=True)
		create_warehouse("_Test Warehouse", company=company)
		item = make_item("_Test Item", {"is_stock_item": 1})

		si = create_sales_invoice(
			customer="_Test Customer",
			company=company,
			item=item.name,
			rate=1000,
			income_account=account.name,
			do_not_submit=True
		)
		si.submit()

		pe = create_payment_entry(
			company=company,
			payment_type="Receive",
			party_type="Customer",
			party="_Test Customer",
			paid_from=account.name,
			paid_to="Cash - _TC",
			paid_amount=1000
		)
		pe.submit()

		gl_credit= frappe.get_all("GL Entry", filters={
			"voucher_type": "Sales Invoice",
			"voucher_no": si.name,
			"account": account.name
		}, fields=["name"], limit=1)[0]
  
		gl_debit = frappe.get_all("GL Entry", filters={
			"voucher_type": "Payment Entry",
			"voucher_no": pe.name,
			"account": account.name
		}, fields=["name"], limit=1)[0]

		glr = frappe.get_doc({
			"doctype": "GL Entry Reconciliation Details",
			"gl_entry": gl_credit.name,
			"parent": gl_credit.name,
			"parentfield": "gl_entry_reconciliation_details",
			"parenttype": "GL Entry",
			"amount": 1000
		}).insert(ignore_permissions=True)
		

		frappe.db.set_value("GL Entry", gl_credit.name, "reconciled_amount", 0)
		frappe.db.set_value("GL Entry", gl_credit.name, "unreconciled_amount", 1000)
		frappe.db.set_value("GL Entry", gl_credit.name, "is_reconciled", 0)

		frappe.db.set_value("GL Entry", gl_debit.name, "reconciled_amount", 600)
		frappe.db.set_value("GL Entry", gl_debit.name, "unreconciled_amount", 400)
		frappe.db.set_value("GL Entry", gl_debit.name, "unreconciled_amount", 400)
		frappe.db.set_value("GL Entry", gl_debit.name, "credit_in_account_currency", 0)
		frappe.db.set_value("GL Entry", gl_debit.name, "debit_in_account_currency", 1000)

		recon = frappe.new_doc("Open Item Reconciliation")
		recon.remove_current_glr_row(
			reconciled_entries=[gl_credit.name],
			unwanted_lines=[]
		)
		gle_debit = frappe.get_doc("GL Entry", gl_debit.name)
		assert gle_debit.reconciled_amount == 600.0
		assert gle_debit.unreconciled_amount == 400.0
		assert gle_debit.is_reconciled == 0
		
		recon.remove_current_glr_row(
			reconciled_entries=[gl_debit.name, gl_credit.name],
			unwanted_lines=[glr.name]
		)
		
		gle_debit.reload()
  
		assert not frappe.db.exists("GL Entry Reconciliation Details", glr.name)
		self.assertEqual(gle_debit.reconciled_amount, 0.0)
		self.assertEqual(gle_debit.unreconciled_amount, 1000.0)
		self.assertEqual(gle_debit.is_reconciled, 0)

		gle_credit = frappe.get_doc("GL Entry", gl_credit.name)
		self.assertEqual(gle_credit.reconciled_amount, 0.0)
		self.assertEqual(gle_credit.unreconciled_amount, 1000.0)
		self.assertEqual(gle_credit.is_reconciled, 0)


def validate_fiscal_year(company):
	from erpnext.accounts.utils import get_fiscal_year

	year = get_fiscal_year(frappe.utils.today())
	if len(year) > 1:
		fiscal_year = frappe.get_doc("Fiscal Year", year[0])
		company_list = {d.company for d in fiscal_year.companies}
		if company not in company_list:
			fiscal_year.append("companies", {"company": company})
			fiscal_year.save()