# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import unittest
import frappe

# test_records = frappe.get_test_records('Mode of Payment')


class TestModeofPayment(unittest.TestCase):
	def test_mode_of_payment_in_payment_entry_TC_ACC_105(self):
		from erpnext.accounts.doctype.sales_invoice.sales_invoice import get_bank_cash_account
		from erpnext.accounts.doctype.payment_entry.test_payment_entry import create_payment_entry

		# Step 1: Get the account for the selected mode of payment (Cash)
		paid_from = get_bank_cash_account("Cash", "_Test Company").get('account')

		# Step 2: Create the payment entry and link it to the correct bank/cash account
		pe = create_payment_entry(paid_from=paid_from)

		# Step 3: Set the mode of payment to 'Cash'
		pe.mode_of_payment = "Cash"
		pe.save()

		# Step 4: Submit the payment entry
		pe.submit()

		# Step 5: Verify that the correct account head in the ledger is affected
		# Fetch ledger entries related to the payment entry
		ledger_entries = frappe.db.sql(
			"""select account, debit, credit, against_voucher
			from `tabGL Entry` where voucher_type='Payment Entry' and voucher_no=%s
			order by account asc""",
			pe.name,
			as_dict=1,
		)

		
		# Check if the ledger entry contains the correct account
		self.assertTrue(
			any(entry.account == paid_from for entry in ledger_entries),
			f"The 'Cash' account ({paid_from}) was not affected in the ledger as expected."
		)

		# Optionally, you can also verify the amount, debit/credit, and other details of the ledger entries
		for entry in ledger_entries:
			if entry.account == paid_from:
				# Here we can add further checks, like verifying the amount and whether it's debit/credit
				self.assertEqual(entry.credit, pe.paid_amount)  # Assuming full payment is being made in Cash

def set_default_account_for_mode_of_payment(mode_of_payment, company, account):
	mode_of_payment.reload()
	if frappe.db.exists(
		"Mode of Payment Account", {"parent": mode_of_payment.mode_of_payment, "company": company}
	):
		frappe.db.set_value(
			"Mode of Payment Account",
			{"parent": mode_of_payment.mode_of_payment, "company": company},
			"default_account",
			account,
		)
		return

	mode_of_payment.append("accounts", {"company": company, "default_account": account})
	mode_of_payment.save()