import frappe
from frappe.tests.utils import FrappeTestCase

class TestTotalStockSummary(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.original_get_value = frappe.db.get_value  # Save original method

	@classmethod
	def tearDownClass(cls):
		frappe.db.get_value = cls.original_get_value  # Restore original after tests
		super().tearDownClass()

	def setUp(self):
		# Restore frappe.db.get_value to prevent leaked lambda
		frappe.db.get_value = self.original_get_value

		hsn_code = "10010010"

		# Create GST HSN Code
		if not frappe.db.exists("GST HSN Code", hsn_code):
			frappe.get_doc({
				"doctype": "GST HSN Code",
				"hsn_code": hsn_code,
				"description": "Test HSN Code for automation"
			}).insert()

		# Ensure UOM exists
		if not frappe.db.exists("UOM", "Nos"):
			frappe.get_doc({"doctype": "UOM", "uom_name": "Nos"}).insert()

		# Create Item
		if not frappe.db.exists("Item", "TEST-STOCK-ITEM"):
			frappe.get_doc({
				"doctype": "Item",
				"item_code": "TEST-STOCK-ITEM",
				"item_name": "Test Stock Item",
				"description": "Description",
				"is_stock_item": 1,
				"stock_uom": "Nos",
				"gst_hsn_code": hsn_code,
			}).insert()

		# Create Company
		if not frappe.db.exists("Company", "Test Company"):
			frappe.get_doc({
				"doctype": "Company",
				"company_name": "Test Company",
				"default_currency": "INR"
			}).insert()

		# Create Warehouse
		if not frappe.db.exists("Warehouse", "Test Warehouse - TC"):
			frappe.get_doc({
				"doctype": "Warehouse",
				"warehouse_name": "Test Warehouse - TC",
				"company": "Test Company"
			}).insert()

		# Create Bin with quantity
		if not frappe.db.exists("Bin", {"item_code": "TEST-STOCK-ITEM", "warehouse": "Test Warehouse - TC"}):
			frappe.get_doc({
				"doctype": "Bin",
				"item_code": "TEST-STOCK-ITEM",
				"warehouse": "Test Warehouse - TC",
				"actual_qty": 25
			}).insert()

	def test_execute_without_filters(self):
		from erpnext.stock.report.total_stock_summary.total_stock_summary import execute

		columns, data = execute()
		assert columns
		assert data
		assert "Company" in columns[0]

	def test_execute_with_group_by_warehouse(self):
		from erpnext.stock.report.total_stock_summary.total_stock_summary import execute

		filters = {"group_by": "Warehouse", "company": "Test Company"}
		columns, data = execute(filters)
		assert columns
		assert data
		assert "Warehouse" in columns[0]

	def test_get_columns_variants(self):
		from erpnext.stock.report.total_stock_summary.total_stock_summary import get_columns

		columns_warehouse = get_columns({"group_by": "Warehouse"})
		assert "Warehouse" in columns_warehouse[0]

		columns_company = get_columns({})
		assert "Company" in columns_company[0]

	def test_get_total_stock_variants(self):
		from erpnext.stock.report.total_stock_summary.total_stock_summary import get_total_stock

		# Without group_by
		data = get_total_stock({})
		assert data
		assert any(float(d[3]) > 0 for d in data)

		# With group_by Warehouse
		data2 = get_total_stock({"group_by": "Warehouse", "company": "Test Company"})
		assert data2
		assert any(float(d[3]) > 0 for d in data2)
