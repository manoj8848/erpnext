import unittest
from datetime import date

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, nowdate

from erpnext.accounts.doctype.payment_entry.test_payment_entry import create_company
from erpnext.accounts.doctype.sales_invoice.test_sales_invoice import create_territory
from erpnext.stock.doctype.item.test_item import create_item
from erpnext.stock.doctype.warehouse.test_warehouse import create_warehouse
from erpnext.stock.report.delayed_item_report.delayed_item_report import DelayedItemReport
from erpnext.stock.report.delayed_order_report.delayed_order_report import DelayedOrderReport, execute


class TestDelayedOrderReport(FrappeTestCase):
	def setUp(self):
		# Create company
		self.company = create_company("_Test Company")
		self.company = "_Test Company"

		# Create warehouse
		self.warehouse = create_warehouse(warehouse_name="_Test Warehouse - _TC", company=self.company)

		# Create item
		self.item_code = create_item(
			item_code="TEST-STOCK-ITEM",
			valuation_rate=100,
			warehouse=self.warehouse,
			company=self.company,
			has_batch_no=1,
		)

		self.batch = frappe.new_doc("Batch")
		self.batch.item = self.item_code
		self.batch.batch_qty = 2
		self.batch.expiry_date = date(2030, 1, 1)
		self.batch.batch_id = "TEST-BATCH-001"
		self.batch.insert()

		# Create price list (avoid currency errors)
		if not frappe.db.exists("Price List", "Test Selling"):
			frappe.get_doc(
				{"doctype": "Price List", "price_list_name": "Test Selling", "selling": 1, "currency": "INR"}
			).insert()

		# Create territory
		create_territory("_Test Territory")

		# Create customer
		if not frappe.db.exists("Customer", "Test Customer"):
			self.customer = frappe.get_doc(
				{
					"doctype": "Customer",
					"customer_name": "Test Customer",
					"customer_group": "Commercial",
					"territory": "_Test Territory",
				}
			).insert()
		else:
			self.customer = frappe.get_doc("Customer", "Test Customer")

		# Ensure currency exchange rate exists
		if not frappe.db.exists("Currency Exchange", {"from_currency": "USD", "to_currency": "INR"}):
			frappe.get_doc(
				{
					"doctype": "Currency Exchange",
					"from_currency": "USD",
					"to_currency": "INR",
					"exchange_rate": 83.0,
					"date": nowdate(),
				}
			).insert()

		self.filters = {
			"based_on": "Sales Invoice",
			"from_date": add_days(nowdate(), -15),
			"to_date": nowdate(),
		}

		# Create two sales orders with different PO numbers
		self.so1 = frappe.get_doc(
			{
				"doctype": "Sales Order",
				"company": self.company,
				"customer": self.customer.name,
				"selling_price_list": "Test Selling",
				"transaction_date": add_days(nowdate(), -10),
				"delivery_date": add_days(nowdate(), -5),  # simulate delayed delivery
				"set_warehouse": self.warehouse,
				"currency": "INR",
				"items": [
					{
						"item_code": self.item_code,
						"qty": 1,
						"rate": 100,
						"batch_no": "TEST-BATCH-001",
					}
				],
				"po_no": "PO-001",
			}
		).insert()
		self.so1.submit()

		self.so2 = frappe.get_doc(
			{
				"doctype": "Sales Order",
				"company": self.company,
				"customer": self.customer.name,
				"selling_price_list": "Test Selling",
				"transaction_date": add_days(nowdate(), -10),
				"delivery_date": add_days(nowdate(), -5),
				"set_warehouse": self.warehouse,
				"currency": "INR",
				"items": [
					{
						"item_code": self.item_code,
						"qty": 1,
						"rate": 200,
						"batch_no": "TEST-BATCH-001",
					}
				],
				"po_no": "PO-002",
			}
		).insert()
		self.so2.submit()

		stock_entry = frappe.get_doc(
			{
				"doctype": "Stock Entry",
				"stock_entry_type": "Material Receipt",
				"company": self.company,
				"to_warehouse": self.warehouse,
				"items": [
					{
						"item_code": self.item_code,
						"qty": 2,
						"rate": 100,
						"t_warehouse": self.warehouse,
						"batch_no": self.batch.name,
					}
				],
			}
		)
		stock_entry.insert()
		stock_entry.submit()

		from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice

		# Create Sales Invoice for so1
		self.si1 = make_sales_invoice(self.so1.name)
		self.si1.posting_date = nowdate()
		self.si1.currency = "INR"
		self.si1.update_stock = 1
		self.si1.set_posting_time = 1
		for item in self.si1.items:
			item.batch_no = self.batch.name
		self.si1.insert()
		self.si1.submit()

		# Create Sales Invoice for so2
		self.si2 = make_sales_invoice(self.so2.name)
		self.si2.posting_date = nowdate()
		self.si2.currency = "INR"
		self.si2.update_stock = 1
		self.si2.set_posting_time = 1
		for item in self.si2.items:
			item.batch_no = self.batch.name
		self.si2.insert()
		self.si2.submit()

		sales_invoice_list = frappe.db.get_list(
			"Sales Invoice", {"posting_date": nowdate(), "company": self.company}, ["name"]
		)
		print("sales_invoice_list", sales_invoice_list)

	def test_get_data_returns_unique_sales_orders_TC_SCK_509(self):
		filters = {
			"based_on": "Sales Invoice",
			"from_date": add_days(nowdate(), -30),
			"to_date": add_days(nowdate(), +30),
			"company": self.company,
		}
		columns, data = execute(filters)

		# Ensure at least one entry exists
		self.assertTrue(len(data) >= 1)

		# Check only one entry per sales order even if multiple items
		so_names = [d.sales_order for d in data]
		self.assertEqual(so_names.count(self.so1.name), 1)

		# Check basic structure
		keys = data[0].keys()
		for field in ["sales_order", "customer", "delivery_date", "grand_total", "po_no"]:
			self.assertIn(field, keys)
