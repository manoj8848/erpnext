# Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today

from erpnext.accounts.doctype.share_transfer.share_transfer import ShareDontExists

test_dependencies = ["Share Type", "Shareholder"]


class TestShareTransfer(FrappeTestCase):
	def setUp(self):
		frappe.db.sql("delete from `tabShare Transfer`")
		frappe.db.sql("delete from `tabShare Balance`")
		share_transfers = [
			{
				"doctype": "Share Transfer",
				"transfer_type": "Issue",
				"date": "2018-01-01",
				"to_shareholder": "SH-00001",
				"share_type": "Equity",
				"from_no": 1,
				"to_no": 500,
				"no_of_shares": 500,
				"rate": 10,
				"company": "_Test Company",
				"asset_account": "Cash - _TC",
				"equity_or_liability_account": "Creditors - _TC",
			},
			{
				"doctype": "Share Transfer",
				"transfer_type": "Transfer",
				"date": "2018-01-02",
				"from_shareholder": "SH-00001",
				"to_shareholder": "SH-00002",
				"share_type": "Equity",
				"from_no": 101,
				"to_no": 200,
				"no_of_shares": 100,
				"rate": 15,
				"company": "_Test Company",
				"equity_or_liability_account": "Creditors - _TC",
			},
			{
				"doctype": "Share Transfer",
				"transfer_type": "Transfer",
				"date": "2018-01-03",
				"from_shareholder": "SH-00001",
				"to_shareholder": "SH-00003",
				"share_type": "Equity",
				"from_no": 201,
				"to_no": 500,
				"no_of_shares": 300,
				"rate": 20,
				"company": "_Test Company",
				"equity_or_liability_account": "Creditors - _TC",
			},
			{
				"doctype": "Share Transfer",
				"transfer_type": "Transfer",
				"date": "2018-01-04",
				"from_shareholder": "SH-00003",
				"to_shareholder": "SH-00002",
				"share_type": "Equity",
				"from_no": 201,
				"to_no": 400,
				"no_of_shares": 200,
				"rate": 15,
				"company": "_Test Company",
				"equity_or_liability_account": "Creditors - _TC",
			},
			{
				"doctype": "Share Transfer",
				"transfer_type": "Purchase",
				"date": "2018-01-05",
				"from_shareholder": "SH-00003",
				"share_type": "Equity",
				"from_no": 401,
				"to_no": 500,
				"no_of_shares": 100,
				"rate": 25,
				"company": "_Test Company",
				"asset_account": "Cash - _TC",
				"equity_or_liability_account": "Creditors - _TC",
			},
		]
		for d in share_transfers:
			st = frappe.get_doc(d)
			st.submit()

	def tearDown(self):
		frappe.db.rollback()

	def test_invalid_share_transfer(self):
		doc = frappe.get_doc(
			{
				"doctype": "Share Transfer",
				"transfer_type": "Transfer",
				"date": "2018-01-05",
				"from_shareholder": "SH-00003",
				"to_shareholder": "SH-00002",
				"share_type": "Equity",
				"from_no": 1,
				"to_no": 100,
				"no_of_shares": 100,
				"rate": 15,
				"company": "_Test Company",
				"equity_or_liability_account": "Creditors - _TC",
			}
		)
		self.assertRaises(ShareDontExists, doc.insert)

		doc = frappe.get_doc(
			{
				"doctype": "Share Transfer",
				"transfer_type": "Purchase",
				"date": "2018-01-02",
				"from_shareholder": "SH-00001",
				"share_type": "Equity",
				"from_no": 1,
				"to_no": 200,
				"no_of_shares": 200,
				"rate": 15,
				"company": "_Test Company",
				"asset_account": "Cash - _TC",
				"equity_or_liability_account": "Creditors - _TC",
			}
		)
		self.assertRaises(ShareDontExists, doc.insert)

	def test_create_share_transfer_and_then_jv_TC_ACC_106(self):
		from erpnext.accounts.doctype.share_transfer.share_transfer import make_jv_entry

		# Create a valid share transfer document (Transfer from SH-00001 to SH-00002)
		doc = frappe.get_doc(
			{
				"doctype": "Share Transfer",
				"transfer_type": "Issue",
				"date": "2025-01-03",
				"to_shareholder": "SH-00003",
				"share_type": "Equity",
				"from_no": 801,
				"to_no": 900,
				"no_of_shares": 100,
				"rate": 15,
				"company": "_Test Company",
				"asset_account": "Cash - _TC",
				"equity_or_liability_account": "Creditors - _TC",
			}
		)
		doc.submit()
		# Assert that the Share Transfer document is successfully submitted
		self.assertEqual(doc.docstatus, 1, "The Share Transfer document was not submitted correctly.")

		amount = doc.no_of_shares * doc.rate
		journal_entry = make_jv_entry(
			company=doc.company,
			account=doc.asset_account,
			amount=amount,
			payment_account=doc.equity_or_liability_account,
			credit_applicant_type="Shareholder",
			credit_applicant=doc.to_shareholder,
			debit_applicant_type="",
			debit_applicant="",
		)
		self.assertEqual(
			journal_entry["accounts"][0]["debit_in_account_currency"],
			amount,
			f"Debit amount in Journal Entry is incorrect. Expected: {amount}, Found: {journal_entry['accounts'][0]['debit_in_account_currency']}",
		)
		self.assertEqual(
			journal_entry["accounts"][1]["credit_in_account_currency"],
			amount,
			f"Credit amount in Journal Entry is incorrect. Expected: {amount}, Found: {journal_entry['accounts'][1]['credit_in_account_currency']}",
		)

	def test_sharetransfer_issue_on_cancel_TC_ACC_238(self):
		# share transfer issue
		get_holders = setup_shareholders()
		issue_doc = get_share_transfer()
		issue_doc.transfer_type = "Issue"
		issue_doc.to_shareholder = get_holders.get("shareholder_1")

		issue_doc.insert(ignore_permissions=True)
		issue_doc.submit()
		self.assertEqual(issue_doc.docstatus, 1)

		shareholder = frappe.get_doc("Shareholder", get_holders.get("shareholder_1"))
		self.assertEqual(shareholder.share_balance[0].no_of_shares, 100)

		# share transfer purchase
		purchase_doc = get_share_transfer()
		purchase_doc.transfer_type = "Purchase"
		purchase_doc.from_shareholder = get_holders.get("shareholder_1")
		purchase_doc.no_of_shares = 50
		purchase_doc.from_no = 500
		purchase_doc.to_no = 549
		purchase_doc.insert(ignore_permissions=True)
		purchase_doc.submit()
		self.assertEqual(purchase_doc.docstatus, 1)

		shareholder.reload()
		self.assertEqual(shareholder.share_balance[0].no_of_shares, 50)

		# share transfer type "Transfer"
		transfer_doc = get_share_transfer()
		transfer_doc.transfer_type = "Transfer"
		transfer_doc.from_shareholder = get_holders.get("shareholder_1")
		transfer_doc.to_shareholder = get_holders.get("shareholder_2")
		transfer_doc.no_of_shares = 50
		transfer_doc.from_no = 550
		transfer_doc.to_no = 599
		transfer_doc.insert(ignore_permissions=True)
		transfer_doc.submit()
		self.assertEqual(transfer_doc.docstatus, 1)

		shareholder.reload()
		self.assertEqual(shareholder.share_balance, [])

		issue_doc.cancel()
		purchase_doc.cancel()
		transfer_doc.cancel()

	def test_basic_validations_TC_ACC_239(self):
		purchase_doc = get_share_transfer()
		purchase_doc.transfer_type = "Purchase"
		purchase_doc.from_shareholder = ""
		purchase_doc.no_of_shares = 50
		purchase_doc.from_no = 500
		purchase_doc.to_no = 549
		with self.assertRaises(frappe.ValidationError) as cm:
			purchase_doc.insert(ignore_permissions=True)
		self.assertIn("The field From Shareholder cannot be blank", str(cm.exception))

	def test_basic_validation_without_account_TC_ACC_240(self):
		get_holders = setup_shareholders()
		issue_doc = get_share_transfer()
		issue_doc.transfer_type = "Issue"
		issue_doc.to_shareholder = get_holders.get("shareholder_1")
		issue_doc.asset_account = ""
		with self.assertRaises(frappe.ValidationError) as cm:
			issue_doc.insert(ignore_permissions=True)
		self.assertIn("The field Asset Account cannot be blank", str(cm.exception))

		issue_doc.asset_account = ("Cash - _TC",)
		issue_doc.to_shareholder = ""

		with self.assertRaises(frappe.ValidationError) as cm:
			issue_doc.insert(ignore_permissions=True)
		self.assertIn("The field To Shareholder cannot be blank", str(cm.exception))

		transfer_doc = get_share_transfer()
		transfer_doc.transfer_type = "Transfer"
		transfer_doc.from_shareholder = ""
		transfer_doc.to_shareholder = ""
		transfer_doc.no_of_shares = 50
		transfer_doc.from_no = 550
		transfer_doc.to_no = 599
		with self.assertRaises(frappe.ValidationError) as cm:
			transfer_doc.insert(ignore_permissions=True)
		self.assertIn("The fields From Shareholder and To Shareholder cannot be blank", str(cm.exception))

		transfer_doc.from_shareholder = get_holders.get("shareholder_1")
		transfer_doc.to_shareholder = get_holders.get("shareholder_2")
		transfer_doc.equity_or_liability_account = ""
		with self.assertRaises(frappe.ValidationError) as cm:
			transfer_doc.insert(ignore_permissions=True)
		self.assertIn("The field Equity/Liability Account cannot be blank", str(cm.exception))

		transfer_doc.equity_or_liability_account = "Creditors - _TC"
		transfer_doc.to_shareholder = get_holders.get("shareholder_1")
		with self.assertRaises(frappe.ValidationError) as cm:
			transfer_doc.insert(ignore_permissions=True)
		self.assertIn("The seller and the buyer cannot be the same", str(cm.exception))

		transfer_doc.to_shareholder = get_holders.get("shareholder_2")
		transfer_doc.no_of_shares = 51
		with self.assertRaises(frappe.ValidationError) as cm:
			transfer_doc.insert(ignore_permissions=True)
		self.assertIn("The number of shares and the share numbers are inconsistent", str(cm.exception))

		transfer_doc.no_of_shares = 50
		transfer_doc.amount = 10
		with self.assertRaises(frappe.ValidationError) as cm:
			transfer_doc.insert(ignore_permissions=True)
		self.assertIn(
			"There are inconsistencies between the rate, no of shares and the amount calculated",
			str(cm.exception),
		)


def setup_shareholders():
	holder_1 = "_Test_Shareholder_1"
	holder_2 = "_Test_Shareholder_2"
	if not frappe.db.exists("Shareholder", holder_1):
		frappe.get_doc({"doctype": "Shareholder", "title": holder_1, "company": "_Test Company"}).insert(
			ignore_permissions=True
		)

	if not frappe.db.exists("Shareholder", holder_2):
		frappe.get_doc({"doctype": "Shareholder", "title": holder_2, "company": "_Test Company"}).insert(
			ignore_permissions=True
		)

	shareholder_1 = frappe.get_doc("Shareholder", {"title": holder_1})
	shareholder_2 = frappe.get_doc("Shareholder", {"title": holder_2})

	return {"shareholder_1": shareholder_1.name, "shareholder_2": shareholder_2.name}


def get_share_transfer():
	return frappe.get_doc(
		{
			"doctype": "Share Transfer",
			"date": today(),
			"share_type": "Equity",
			"from_no": 500,
			"to_no": 599,
			"no_of_shares": 100,
			"rate": 15,
			"company": "_Test Company",
			"asset_account": "Cash - _TC",
			"equity_or_liability_account": "Creditors - _TC",
		}
	)
