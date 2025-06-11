import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.stock.report.stock_and_account_value_comparison.stock_and_account_value_comparison import execute
from erpnext.accounts.doctype.payment_entry.test_payment_entry import create_company
from erpnext.stock.doctype.warehouse.test_warehouse import create_warehouse
from erpnext.stock.doctype.item.test_item import create_item
from erpnext.stock.doctype.stock_entry.test_stock_entry import get_or_create_fiscal_year

class TestStockAndAccountValueComparison(FrappeTestCase):
	def setUp(self):
		if not frappe.db.exists("Company", "_Test Company"):
			create_company("_Test Company")
		self.company = "_Test Company"
		self.account = "Stock In Hand - _TC"
		self.posting_date = frappe.utils.nowdate()
		self.warehouse = create_warehouse(warehouse_name="_Test Warehouse - _TC", company=self.company)
		self.item = create_item(item_code="_Test Item", valuation_rate=100)
		get_or_create_fiscal_year(self.company)
		self.stock_entry = self.create_stock_entry()
		self.create_stock_ledger_entry()
		self.create_gl_entry()


	def test_report_execute_and_columns_and_data(self):
		filters = frappe._dict({"company": self.company, "as_on_date": self.posting_date})
		columns, data = execute(filters)
		# Columns structure
		self.assertTrue(columns)
		self.assertIn("fieldname", columns[0])
		expected_fields = [
			"name", "posting_date", "posting_time", "voucher_type", "voucher_no",
			"stock_value", "account_value", "difference_value"
		]
		self.assertEqual([col["fieldname"] for col in columns], expected_fields)
		# Data is returned and has required fields
		self.assertTrue(data)
		for row in data:
			for key in ["stock_value", "account_value", "difference_value", "voucher_type", "voucher_no"]:
				self.assertIn(key, row)
		# Difference logic
		for row in data:
			self.assertAlmostEqual(row["difference_value"], row["stock_value"] - row["account_value"], places=2)

	def test_report_execute_with_account_filter(self):
		filters = frappe._dict({
			"company": self.company,
			"as_on_date": self.posting_date,
			"account": self.account
		})
		columns, data = execute(filters)
		self.assertTrue(data)
		for row in data:
			self.assertIn("account_value", row)
			self.assertIn("stock_value", row)

	def test_report_perpetual_inventory_disabled(self):
		import erpnext
		filters = frappe._dict({"company": self.company, "as_on_date": self.posting_date})
		original = erpnext.is_perpetual_inventory_enabled
		erpnext.is_perpetual_inventory_enabled = lambda company: False
		with self.assertRaises(frappe.ValidationError):
			execute(filters)
		erpnext.is_perpetual_inventory_enabled = original

	def test_data_difference_filtering(self):
		# Manipulate GL Entry to force a difference > 0.1
		frappe.db.set_value(
			"GL Entry",
			{"voucher_no": self.stock_entry},
			"debit_in_account_currency",
			800,  # stock_value is 1000, so difference will be 200
		)
		filters = frappe._dict({"company": self.company, "as_on_date": self.posting_date})
		_, data = execute(filters)
		self.assertTrue(any(abs(row["difference_value"]) > 0.1 for row in data))

	def test_posting_time_conversion(self):
		filters = frappe._dict({"company": self.company, "as_on_date": self.posting_date})
		_, data = execute(filters)
		for row in data:
			if "posting_time" in row and row["posting_time"] is not None:
				from datetime import timedelta
				self.assertIsInstance(row["posting_time"], timedelta)

	def test_create_reposting_entries(self):
		from erpnext.stock.report.stock_and_account_value_comparison.stock_and_account_value_comparison import create_reposting_entries

		# Simulate report output row for reposting
		test_row = {
			"voucher_type": "Stock Entry",
			"voucher_no": self.stock_entry,
			"posting_date": self.posting_date
		}

		# Ensure no pre-existing repost entry
		existing = frappe.get_all(
			"Repost Item Valuation",
			filters={
				"voucher_type": test_row["voucher_type"],
				"voucher_no": test_row["voucher_no"],
				"company": self.company,
			}
		)
		for r in existing:
			doc = frappe.get_doc("Repost Item Valuation", r.name)
			if doc.docstatus == 1:
				doc.cancel()
			doc.delete()

		# Execute the function
		create_reposting_entries([test_row], self.company)

		# Fetch the created repost document
		repost_docs = frappe.get_all(
			"Repost Item Valuation",
			filters={
				"voucher_type": test_row["voucher_type"],
				"voucher_no": test_row["voucher_no"],
				"company": self.company,
			},
			fields=["name", "status", "based_on", "docstatus", "voucher_type", "voucher_no", "posting_date"]
		)

		# Assertions
		self.assertEqual(len(repost_docs), 1, "Expected one Repost Item Valuation to be created.")

		repost_doc = repost_docs[0]

		# self.assertEqual(repost_doc["status"], "Queued", "Repost Item Valuation should be in 'Queued' status.")
		self.assertEqual(repost_doc["based_on"], "Transaction", "Repost should be based on 'Transaction'.")
		self.assertEqual(repost_doc["docstatus"], 1, "Repost Item Valuation should be submitted (docstatus=1).")
		self.assertEqual(repost_doc["voucher_type"], test_row["voucher_type"], "Voucher type should match input.")
		self.assertEqual(repost_doc["voucher_no"], test_row["voucher_no"], "Voucher no should match input.")
		self.assertEqual(str(repost_doc["posting_date"]), str(self.posting_date), "Posting date should match input.")


	def create_stock_entry(self):
		se = frappe.get_doc(
			{
				"doctype": "Stock Entry",
				"stock_entry_type": "Material Receipt",
				"company": self.company,
				"posting_date": self.posting_date,
				"items": [
					{
						"item_code": self.item.name,
						"qty": 10,
						"uom": "Nos",
						"t_warehouse": self.warehouse,
						"rate": 100,
					}
				],
			}
		)
		se.insert(ignore_permissions=True)
		se.submit()
		return se.name

	def create_stock_ledger_entry(self):
		if not frappe.db.exists("Stock Ledger Entry", {"voucher_no": self.stock_entry}):
			frappe.get_doc(
				{
					"doctype": "Stock Ledger Entry",
					"item_code": self.item.name,
					"warehouse": self.warehouse,
					"posting_date": self.posting_date,
					"posting_time": frappe.utils.now_datetime().time(),
					"voucher_type": "Stock Entry",
					"voucher_no": self.stock_entry,
					"voucher_detail_no": self.stock_entry + "-ROW1",
					"actual_qty": 10,
					"stock_value": 1000,
					"stock_value_difference": 1000,
					"company": self.company,
					"incoming_rate": 100,
					"is_cancelled": 0,
				}
			).insert(ignore_permissions=True)

	def create_gl_entry(self):
		if not frappe.db.exists("GL Entry", {"voucher_no": self.stock_entry}):
			frappe.get_doc(
				{
					"doctype": "GL Entry",
					"posting_date": self.posting_date,
					"account": self.account,
					"debit_in_account_currency": 1000,
					"credit_in_account_currency": 0,
					"voucher_type": "Stock Entry",
					"voucher_no": self.stock_entry,
					"company": self.company,
					"fiscal_year": frappe.defaults.get_user_default("fiscal_year"),
				}
			).insert(ignore_permissions=True)