# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

from random import randint

import frappe
from frappe import _
from frappe.tests.utils import FrappeTestCase, change_settings
from frappe.utils.data import add_days, today

from erpnext.selling.doctype.sales_order.test_sales_order import make_sales_order
from erpnext.stock.doctype.stock_reservation_entry.test_stock_reservation_entry import (
	cancel_all_stock_reservation_entries,
	create_items,
	create_material_receipt,
)
from erpnext.stock.doctype.warehouse.test_warehouse import create_warehouse
from erpnext.stock.report.reserved_stock.reserved_stock import execute as reserved_stock_report


class TestReservedStock(FrappeTestCase):
	def setUp(self) -> None:
		from erpnext.accounts.doctype.payment_entry.test_payment_entry import create_company

		create_company()
		super().setUp()
		self.stock_qty = 100
		self.warehouse = create_warehouse("_Test Warehouse - _TC", "_Test Company")

	def tearDown(self) -> None:
		cancel_all_stock_reservation_entries()
		return super().tearDown()

	@change_settings(
		"Stock Settings",
		{
			"allow_negative_stock": 0,
			"enable_stock_reservation": 1,
			"auto_reserve_serial_and_batch": 1,
			"pick_serial_and_batch_based_on": "FIFO",
		},
	)
	def test_reserved_stock_report(self):
		items_details = create_items()
		create_material_receipt(items_details, self.warehouse, qty=self.stock_qty)

		for item_code, properties in items_details.items():
			so = make_sales_order(
				item_code=item_code, qty=randint(11, 100), warehouse=self.warehouse, uom=properties.stock_uom
			)
			so.create_stock_reservation_entries()

		columns, data = reserved_stock_report(
			filters={
				"company": so.company,
				"from_date": today(),
				"to_date": today(),
			}
		)

		self.assertTrue(columns)
		self.assertTrue(data)
		self.assertIn("item_code", [col["fieldname"] for col in columns])
		self.assertEqual(len(data), len(items_details))

	def test_missing_filters_throws_T_RS_001(self):
		with self.assertRaises(frappe.ValidationError, msg="Please set filters"):
			reserved_stock_report(filters=None)

	def test_missing_individual_filters_T_RS_002(self):
		with self.assertRaises(frappe.ValidationError, msg="Please set company"):
			reserved_stock_report(filters={"from_date": today(), "to_date": today()})

		with self.assertRaises(frappe.ValidationError, msg="Please set from_date"):
			reserved_stock_report(filters={"company": "Test Company", "to_date": today()})

		with self.assertRaises(frappe.ValidationError, msg="Please set to_date"):
			reserved_stock_report(filters={"company": "Test Company", "from_date": today()})

	def test_invalid_date_range_T_RS_003(self):
		with self.assertRaises(frappe.ValidationError, msg="From Date cannot be greater than To Date"):
			reserved_stock_report(
				filters={
					"company": "Test Company",
					"from_date": today(),
					"to_date": add_days(today(), -1),
				}
			)
