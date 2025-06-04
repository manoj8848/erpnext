import unittest

import frappe
from frappe.utils import getdate

from erpnext.accounts.doctype.sales_invoice.test_sales_invoice import create_sales_invoice
from erpnext.accounts.report.account_balance.account_balance import execute


class TestAccountBalance(unittest.TestCase):
	def test_account_balance(self):
		frappe.db.sql("delete from `tabSales Invoice` where company='_Test Company'")
		frappe.db.sql("delete from `tabGL Entry` where company='_Test Company'")

		filters = {
			"company": "_Test Company",
			"report_date": getdate(),
			"root_type": "Income"
		}

		make_sales_invoice()

		report = execute(filters)

		expected_data = [
			{
				"account": "Direct Income - _TC",
				"currency": "INR",
				"balance": -100.0,
			},
			{
				"account": "Income - _TC",
				"currency": "INR",
				"balance": -100.0,
			},
			{
				"account": "Indirect Income - _TC",
				"currency": "INR",
				"balance": 0.0,
			},
			{
				"account": "Sales - _TC",
				"currency": "INR",
				"balance": -100.0,
			},
			{
				"account": "Service - _TC",
				"currency": "INR",
				"balance": 0.0,
			},
			{
				"account": "_Test Account Sales - _TC",
				"currency": "INR",
				"balance": 0.0,
			},
		]
		self.assertEqual(expected_data, report[1])


def make_sales_invoice():
	frappe.set_user("Administrator")

	create_sales_invoice(
		company="_Test Company",
		customer="_Test Customer",
		currency="INR",
		warehouse="Finished Goods - _TC",
		debit_to="Debtors - _TC",
		income_account="Sales - _TC",
		expense_account="Cost of Goods Sold - _TC",
		cost_center="Main - _TC",
	)
