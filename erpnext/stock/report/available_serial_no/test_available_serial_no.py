# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import frappe
from frappe import _dict
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from erpnext.stock.doctype.delivery_note.test_delivery_note import create_delivery_note
from erpnext.stock.doctype.item.test_item import create_item
from erpnext.stock.doctype.purchase_receipt.test_purchase_receipt import make_purchase_receipt
from erpnext.stock.doctype.stock_entry.test_stock_entry import make_stock_entry
from erpnext.stock.report.available_serial_no.available_serial_no import execute


class TestStockLedgerReport(FrappeTestCase):
	def setUp(self) -> None:
		from erpnext.stock.doctype.warehouse.test_warehouse import create_warehouse

		self.item = create_item("_Test Item with Serial No", is_stock_item=1)
		self.item.has_serial_no = 1
		self.item.serial_no_series = "TEST.###"
		self.item.valuation_rate = 100
		self.item.save(ignore_permissions=True)
		self.item1 = create_item("_Test Item without Serial No", is_stock_item=1)
		self.item1.valuation_rate = 100
		self.item1.save(ignore_permissions=True)

		self.default_warehouse = create_warehouse("_Test Warehouse - _TC", "_Test Company")
		self.alt_warehouse = create_warehouse("_Test Warehouse 1 - _TC", "_Test Company")

		self.filters = frappe._dict(
			company="_Test Company",
			from_date=today(),
			to_date=add_days(today(), 30),
			item_code="_Test Item with Serial No",
		)

	def tearDown(self) -> None:
		frappe.db.rollback()

	def test_available_serial_no(self):
		report = frappe.get_doc("Report", "Available Serial No")

		make_purchase_receipt(qty=10, item_code="_Test Item with Serial No")
		data = report.get_data(filters=self.filters)
		serial_nos = [item for item in data[-1][-1]["balance_serial_no"].split("\n")]

		self.assertEqual(len(serial_nos), 10)

		create_delivery_note(qty=5, item_code="_Test Item with Serial No")
		data = report.get_data(filters=self.filters)
		serial_nos = [item for item in data[-1][-1]["balance_serial_no"].split("\n")]

		self.assertEqual(len(serial_nos), 5)
		self.assertEqual(data[1][0]["voucher_type"], "Purchase Receipt")
		self.assertEqual(data[1][1]["voucher_type"], "Delivery Note")

	def test_available_serial_no_with_include_uom_T_ASN_001(self):
		from erpnext.stock.report.available_serial_no.available_serial_no import execute

		self.filters.include_uom = 1

		columns, data = execute(filters=self.filters)

		uom_column_found = any(
			"UOM" in col.get("label", "") if isinstance(col, dict) else "UOM" in str(col) for col in columns
		)
		self.assertTrue(uom_column_found)

	def test_report_skips_items_with_no_serial_nos_T_ASN_002(self):
		serialized_item = self.item

		non_serialized_item = create_item("_Test Item with No Serial No", is_stock_item=1)

		se1 = make_stock_entry(
			item_code=serialized_item.name,
			target="Stores - _TC",
			qty=5,
			basic_rate=100,
		)
		se1.submit()

		se2 = make_stock_entry(
			item_code=non_serialized_item.name,
			target="Stores - _TC",
			qty=5,
			basic_rate=100,
		)
		se2.submit()

		filters = _dict(
			{
				"company": "_Test Company",
				"from_date": today(),
				"to_date": today(),
				"valuation_field_type": "Float",
			}
		)

		columns, data = execute(filters=filters)
		item_codes_in_report = [row.get("item_code") for row in data]

		self.assertIn(serialized_item.name, item_codes_in_report)
		self.assertNotIn(non_serialized_item.name, item_codes_in_report)

	def test_no_rows_returned_if_no_balance_serials_T_ASN_003(self):
		se1 = make_stock_entry(
			item_code=self.item.name, target="Stores - _TC", purpose="Material Receipt", qty=1, basic_rate=100
		)
		se = make_stock_entry(
			item_code=self.item.name,
			source="Stores - _TC",
			purpose="Material Issue",
			qty=1,
			basic_rate=100,
			do_not_submit=True,
		)
		se.items[0].serial_no = se1.items[0].serial_no
		se.submit()

		filters = _dict(
			{
				"company": "_Test Company",
				"from_date": today(),
				"to_date": today(),
				"valuation_field_type": "Float",
			}
		)

		columns, data = execute(filters=filters)

		self.assertEqual(data[1]["qty_after_transaction"], 0)

	def test_multiple_transactions_and_warehouses_T_ASN_004(self):
		report = frappe.get_doc("Report", "Available Serial No")

		make_purchase_receipt(qty=5, item_code="_Test Item with Serial No", warehouse=self.default_warehouse)
		make_purchase_receipt(qty=3, item_code="_Test Item with Serial No", warehouse=self.alt_warehouse)

		data = report.get_data(filters=self.filters)
		serial_nos = [sn for i in data[1] for sn in i["balance_serial_no"].split("\n")]

		self.assertEqual(len(serial_nos), 8)

	def test_serial_balance_after_sales_return_T_ASN_005(self):
		from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_return

		report = frappe.get_doc("Report", "Available Serial No")

		make_purchase_receipt(qty=5, item_code="_Test Item with Serial No")
		dn = create_delivery_note(qty=5, item_code="_Test Item with Serial No")
		make_sales_return(dn.name)

		data = report.get_data(filters=self.filters)
		balance_serials = [sn for i in data[1] for sn in i["balance_serial_no"].split("\n") if sn.strip()]
		self.assertEqual(len(balance_serials), 5)

	def test_serial_balance_after_purchase_return_T_ASN_006(self):
		from erpnext.stock.doctype.purchase_receipt.purchase_receipt import make_purchase_return

		report = frappe.get_doc("Report", "Available Serial No")

		pr = make_purchase_receipt(qty=5, item_code="_Test Item with Serial No")
		pr_ret = make_purchase_return(pr.name)
		pr_ret.insert()
		pr_ret.submit()

		data = report.get_data(filters=self.filters)
		balance_serials = [sn.strip() for sn in data[-1][-1]["balance_serial_no"].split("\n") if sn.strip()]

		self.assertEqual(balance_serials, [])

	def test_stock_transfer_between_warehouses_T_ASN_007(self):
		report = frappe.get_doc("Report", "Available Serial No")

		make_purchase_receipt(qty=5, item_code="_Test Item with Serial No", warehouse=self.default_warehouse)
		make_stock_entry(
			item_code="_Test Item with Serial No",
			qty=5,
			from_warehouse=self.default_warehouse,
			to_warehouse=self.alt_warehouse,
			purpose="Material Transfer",
		)

		data = report.get_data(filters=self.filters)
		serials_in_alt_wh = [d for d in data[1] if d.get("warehouse") == self.alt_warehouse]
		serials = serials_in_alt_wh[-1]["balance_serial_no"].split("\n")

		self.assertEqual(len(serials), 5)

	def test_invalid_item_code_T_ASN_008(self):
		with self.assertRaises(Exception):
			execute(filters=_dict({"item_code": "Non-Existent Item"}))

	def test_valuation_and_qty_fields_T_ASN_009(self):
		report = frappe.get_doc("Report", "Available Serial No")

		make_purchase_receipt(qty=3, item_code="_Test Item with Serial No")
		data = report.get_data(filters=self.filters)

		last_row = data[-1][-1]
		self.assertGreaterEqual(last_row["qty_after_transaction"], 0)
		self.assertIn("in_out_rate", last_row)
		self.assertIn("valuation_rate", last_row)

	def test_update_stock_ledger_entry_with_batch_no_T_ASN_010(self):
		from frappe.utils import flt

		from erpnext.stock.report.available_serial_no.available_serial_no import update_stock_ledger_entry

		sle = frappe._dict(
			item_code="_Test Item with Serial No",
			company="_Test Company",
			actual_qty=5,
			stock_value_difference=500,
			qty_after_transaction=0,
			stock_value=0,
			voucher_type="Purchase Receipt",
			batch_no="BATCH-001",
		)
		item_details = {"_Test Item with Serial No": {"item_name": "Test Item", "description": "Test"}}
		filters = {"batch_no": "BATCH-001"}
		batch_balance_dict = {}
		precision = 2

		actual_qty = 0
		stock_value = 0

		update_stock_ledger_entry(
			sle, item_details, filters, actual_qty, stock_value, batch_balance_dict, precision
		)

		self.assertEqual(sle.qty_after_transaction, 5)
		self.assertEqual(sle.stock_value, 500)
		self.assertEqual(sle.in_out_rate, flt(500 / 5, precision))
		self.assertIn("BATCH-001", batch_balance_dict)
		self.assertEqual(batch_balance_dict["BATCH-001"][0], 5)

	def test_update_stock_ledger_entry_stock_reconciliation_T_ASN_011(self):
		from erpnext.stock.report.available_serial_no.available_serial_no import update_stock_ledger_entry

		sle = frappe._dict(
			item_code="_Test Item with Serial No",
			company="_Test Company",
			actual_qty=0,
			qty_after_transaction=8,
			stock_value=800,
			stock_value_difference=0,
			voucher_type="Stock Reconciliation",
		)
		item_details = {"_Test Item with Serial No": {"item_name": "Test Item", "description": "Test"}}
		filters = {"item_code": "_Test Item with Serial No"}
		batch_balance_dict = {}
		precision = 2

		actual_qty = 0
		stock_value = 0

		update_stock_ledger_entry(
			sle, item_details, filters, actual_qty, stock_value, batch_balance_dict, precision
		)

		self.assertEqual(sle.qty_after_transaction, 8)
		self.assertEqual(sle.stock_value, 800)
		self.assertIn("in_out_rate", sle)

	def test_in_out_rate_divide_by_zero_T_ASN_012(self):
		from erpnext.stock.report.available_serial_no.available_serial_no import update_stock_ledger_entry

		sle = frappe._dict(
			item_code="_Test Item with Serial No",
			company="_Test Company",
			actual_qty=0,
			qty_after_transaction=5,
			stock_value=100,
			stock_value_difference=0,
			voucher_type="Delivery Note",
		)
		item_details = {"_Test Item with Serial No": {"item_name": "Test Item", "description": "Test"}}
		filters = {"item_code": "_Test Item with Serial No"}
		batch_balance_dict = {}
		precision = 2

		update_stock_ledger_entry(sle, item_details, filters, 0, 0, batch_balance_dict, precision)

	def test_opening_balance_with_batch_filter_T_ASN_013(self):
		from erpnext.stock.report.available_serial_no import available_serial_no

		make_purchase_receipt(qty=3, item_code="_Test Item with Serial No")
		batch_no = frappe.db.get_value(
			"Stock Ledger Entry",
			{"item_code": "_Test Item with Serial No", "voucher_type": "Purchase Receipt"},
			"batch_no",
		)

		filters = frappe._dict(
			company="_Test Company",
			from_date=today(),
			to_date=add_days(today(), 30),
			item_code="_Test Item with Serial No",
			batch_no=batch_no,
		)

		columns, data = available_serial_no.execute(filters=filters)

		self.assertIsInstance(columns, list)
		self.assertIsInstance(data, list)

	def test_update_stock_ledger_entry_stock_reconciliation_T_ASN_014(self):
		from erpnext.stock.report.available_serial_no.available_serial_no import update_stock_ledger_entry

		sle = frappe._dict(
			item_code="_Test Item with Serial No",
			company="_Test Company",
			actual_qty=0,
			qty_after_transaction=8,
			stock_value=800,
			stock_value_difference=0,
			voucher_type="Stock Reconciliation",
		)
		item_details = {"_Test Item with Serial No": {"item_name": "Test Item", "description": "Test"}}
		filters = {"item_code": "_Test Item with Serial No"}
		batch_balance_dict = {}
		precision = 2

		actual_qty = 0
		stock_value = 0

		update_stock_ledger_entry(
			sle, item_details, filters, actual_qty, stock_value, batch_balance_dict, precision
		)

		self.assertEqual(sle.qty_after_transaction, 8)
		self.assertEqual(sle.stock_value, 800)
		self.assertIn("in_out_rate", sle)
