# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today

from erpnext.accounts.report.balance_sheet.balance_sheet import execute


class TestBalanceSheet(FrappeTestCase):
	def test_balance_sheet(self):
		from erpnext.accounts.doctype.purchase_invoice.test_purchase_invoice import make_purchase_invoice
		from erpnext.accounts.doctype.sales_invoice.test_sales_invoice import (
			create_sales_invoice,
		)

		frappe.db.sql("delete from `tabPurchase Invoice` where company='_Test Company'")
		frappe.db.sql("delete from `tabSales Invoice` where company='_Test Company'")
		frappe.db.sql("delete from `tabGL Entry` where company='_Test Company'")

		make_purchase_invoice(
			company="_Test Company",
			warehouse="Finished Goods - _TC",
			expense_account="Cost of Goods Sold - _TC",
			cost_center="Main - _TC",
			qty=10,
			rate=100,
		)
		create_sales_invoice(
			company="_Test Company",
			debit_to="Debtors - _TC",
			income_account="Sales - _TC",
			cost_center="Main - _TC",
			qty=5,
			rate=110,
		)
		filters = frappe._dict(
			company="_Test Company",
			period_start_date=today(),
			period_end_date=today(),
			periodicity="Yearly",
		)
		result = execute(filters)[1]
		for account_dict in result:
			if account_dict.get("account") == "Current Liabilities - _TC":
				self.assertEqual(account_dict.total, 1000)
			if account_dict.get("account") == "Current Assets - _TC":
				self.assertEqual(account_dict.total, 750)
