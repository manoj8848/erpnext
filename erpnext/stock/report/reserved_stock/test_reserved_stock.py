# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

from random import randint
import frappe
from frappe.tests.utils import FrappeTestCase, change_settings
from frappe.utils.data import today, add_days
from frappe import _

from erpnext.selling.doctype.sales_order.test_sales_order import make_sales_order
from erpnext.stock.doctype.stock_reservation_entry.test_stock_reservation_entry import (
	cancel_all_stock_reservation_entries,
	create_items,
	create_material_receipt,
)
from erpnext.stock.report.reserved_stock.reserved_stock import execute as reserved_stock_report


class TestReservedStock(FrappeTestCase):
	def setUp(self) -> None:
		super().setUp()
		self.stock_qty = 100
		self.warehouse = "_Test Warehouse - _TC"

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

	def test_missing_filters_throws(self):
		with self.assertRaises(frappe.ValidationError) as cm:
			reserved_stock_report(filters=None)
		self.assertIn("Please set filters", str(cm.exception))

	def test_missing_individual_filters(self):
		with self.assertRaises(frappe.ValidationError) as cm:
			reserved_stock_report(filters={"from_date": today(), "to_date": today()})
		self.assertIn("Please set company", str(cm.exception))

		with self.assertRaises(frappe.ValidationError) as cm:
			reserved_stock_report(filters={"company": "Test Company", "to_date": today()})
		self.assertIn("Please set from_date", str(cm.exception))

		with self.assertRaises(frappe.ValidationError) as cm:
			reserved_stock_report(filters={"company": "Test Company", "from_date": today()})
		self.assertIn("Please set to_date", str(cm.exception))

	def test_invalid_date_range(self):
		with self.assertRaises(frappe.ValidationError) as cm:
			reserved_stock_report(
				filters={
					"company": "Test Company",
					"from_date": today(),
					"to_date": add_days(today(), -1),
				}
			)
		self.assertIn("From Date cannot be greater than To Date", str(cm.exception))
