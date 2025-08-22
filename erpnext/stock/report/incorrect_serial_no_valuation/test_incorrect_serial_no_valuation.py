import unittest

import frappe
from frappe import _
from frappe.utils import nowdate, today

from erpnext.stock.report.incorrect_serial_no_valuation.incorrect_serial_no_valuation import (
	execute as report_execute,
)


class TestIncorrectSerialNoValuationReport(unittest.TestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		from erpnext.stock.doctype.item.test_item import create_item

		self.item = create_item("Test Serial Valuation", {"has_serial_no": 1, "is_stock_item": 1})
		self.item.is_stock_item = 1
		self.item.has_serial_no = 1
		self.item.valuation_rate = 100
		self.item.serial_no_series = "TEST-SN-.#####"
		self.item.save()
		self.warehouse = "_Test Warehouse - _TC"
		self.company = "_Test Company"

	def _make_material_issue(self, serial_no, qty=1, rate=100, voucher_no=None):
		se = frappe.get_doc(
			{
				"doctype": "Stock Entry",
				"stock_entry_type": "Material Issue",
				"company": self.company,
				"posting_date": today(),
				"items": [
					{
						"item_code": self.item.name,
						"qty": qty,
						"s_warehouse": self.warehouse,
						"uom": "Nos",
						"conversion_factor": 1,
						"basic_rate": rate,
						"serial_no": serial_no,
					}
				],
			}
		)
		if voucher_no:
			se.name = voucher_no
		se.insert()
		se.submit()
		return se.name

	def _make_stock_issue_with_serial(self, serial_no, rate=150):
		stock_entry = frappe.get_doc(
			{
				"doctype": "Stock Entry",
				"stock_entry_type": "Material Issue",
				"company": self.company,
				"items": [
					{
						"item_code": self.item.name,
						"qty": 1,
						"s_warehouse": self.warehouse,
						"uom": "Nos",
						"conversion_factor": 1,
						"basic_rate": rate,
						"serial_no": serial_no,
					}
				],
			}
		)
		stock_entry.insert()
		stock_entry.submit()
		return stock_entry.name

	def _make_serial_no(self, rate=100):
		item = self.item.name
		se = frappe.get_doc(
			{
				"doctype": "Stock Entry",
				"stock_entry_type": "Material Receipt",
				"company": self.company,
				"items": [
					{
						"item_code": item,
						"qty": 1,
						"t_warehouse": self.warehouse,
						"uom": "Nos",
						"conversion_factor": 1,
						"basic_rate": rate,
					}
				],
			}
		)
		se.insert()
		se.submit()

		serial_nos = frappe.db.get_value("Stock Entry Detail", {"parent": se.name}, "serial_no")
		serial_no = serial_nos.split("\n")[0] if serial_nos else None

		return serial_no, se.name

	def _make_stock_entry(self, serial_no, qty=1, rate=100, voucher_no=None):
		se = frappe.get_doc(
			{
				"doctype": "Stock Entry",
				"stock_entry_type": "Material Receipt",
				"company": self.company,
				"posting_date": today(),
				"items": [
					{
						"item_code": self.item.name,
						"qty": qty,
						"t_warehouse": self.warehouse,
						"uom": "Nos",
						"conversion_factor": 1,
						"basic_rate": rate,
						"serial_no": serial_no,
					}
				],
			}
		)
		if voucher_no:
			se.name = voucher_no
		se.insert()
		se.submit()
		return se.name

	def _make_sle(self, serial_no, actual_qty, incoming_rate, voucher_no):
		sle = frappe.get_doc(
			{
				"doctype": "Stock Ledger Entry",
				"item_code": self.item.name,
				"warehouse": self.warehouse,
				"posting_date": today(),
				"posting_time": "10:00",
				"voucher_type": "Stock Entry",
				"voucher_no": voucher_no,
				"actual_qty": actual_qty,
				"incoming_rate": incoming_rate,
				"company": self.company,
				"stock_uom": "Nos",
				"serial_no": serial_no,
			}
		)
		sle.insert()
		sle.submit()

	def test_empty_filters_returns_balance_row_only_TC_SCK_479(self):
		columns, data = report_execute({})
		self.assertEqual(len(data), 1)
		self.assertEqual(data[0].get("serial_no"), frappe.bold(_("Balance")))
		self.assertEqual(data[0].get("qty"), 0)
		self.assertEqual(data[0].get("valuation_rate"), 0)

	def test_balanced_serial_no_excluded_TC_SCK_480(self):
		serial_no = "SN-BAL-001"
		self._make_stock_entry(serial_no, qty=1, rate=100, voucher_no="TEST-SN-BAL-IN")
		out_entry = frappe.get_doc(
			{
				"doctype": "Stock Entry",
				"stock_entry_type": "Material Issue",
				"company": self.company,
				"posting_date": today(),
				"items": [
					{
						"item_code": self.item.name,
						"qty": 1,
						"s_warehouse": self.warehouse,
						"uom": "Nos",
						"conversion_factor": 1,
						"basic_rate": 100,
						"serial_no": serial_no,
					}
				],
			}
		)
		out_entry.insert()
		out_entry.submit()

		columns, data = report_execute({"item_code": self.item.name})
		serials = [row.get("serial_no") for row in data]

		self.assertNotIn(serial_no, serials[:-1])
		self.assertEqual(data[-1].get("serial_no"), frappe.bold(_("Balance")))

	def test_negative_qty_triggers_incorrect_TC_SCK_481(self):
		from frappe.utils import add_days

		serial_no = "SN-NEG-QTY-NEW"
		today = frappe.utils.nowdate()
		backdated_posting_date = add_days(today, -5)

		if not frappe.db.exists("Serial No", serial_no):
			serial = frappe.new_doc("Serial No")
			serial.update(
				{
					"serial_no": serial_no,
					"item_code": self.item.name,
					"purchase_document_type": "Stock Entry",
					"purchase_document_no": "TEST-SN-BAL-FAKE",
				}
			)
			serial.flags.ignore_mandatory = True
			serial.flags.ignore_permissions = True
			serial.insert(ignore_permissions=True)

			frappe.db.set_value("Serial No", serial.name, "warehouse", self.warehouse)

		sle = frappe.new_doc("Stock Ledger Entry")
		sle.update(
			{
				"item_code": self.item.name,
				"warehouse": self.warehouse,
				"posting_date": backdated_posting_date,
				"posting_time": "12:00:00",
				"qty_after_transaction": -1,
				"actual_qty": -1,
				"stock_value_difference": -100,
				"incoming_rate": 100,
				"serial_no": serial_no,
				"voucher_type": "Stock Entry",
				"voucher_no": "TEST-SN-BAL-FAKE",
				"company": self.company,
			}
		)
		sle.flags.ignore_permissions = True
		sle.flags.ignore_validate = True
		sle.flags.ignore_links = True
		sle.insert(ignore_permissions=True)

		columns, data = report_execute({"item_code": self.item.name})
		serials = [row.get("serial_no") for row in data]
		self.assertIn(serial_no, serials)

		total_indexes = [i for i, row in enumerate(data) if row.get("serial_no") == frappe.bold(_("Total"))]
		self.assertTrue(len(total_indexes) > 0)
		self.assertEqual(data[-1].get("serial_no"), frappe.bold(_("Balance")))

	def test_multiple_serial_nos_TC_SCK_482(self):
		serial_no_1, _ = self._make_serial_no(rate=100)
		serial_no_2, _ = self._make_serial_no(rate=150)
		serial_no_2, stock_entry_2 = self._make_serial_no(rate=150)

		frappe.db.sql("DELETE FROM `tabStock Ledger Entry` WHERE serial_no = %s", serial_no_2)

		self._make_sle(serial_no_2, 1, 0, voucher_no=stock_entry_2)

		from erpnext.stock.report.incorrect_serial_no_valuation import incorrect_serial_no_valuation as report

		data = report.execute({})[1]

		result = [row for row in data if row.get("serial_no") in [serial_no_1, serial_no_2]]

		self.assertEqual(len(result), 1)
		self.assertEqual(result[0]["serial_no"], serial_no_2)
		self.assertEqual(result[0]["valuation_rate"], 0)

	def test_missing_serial_no_is_ignored_TC_SCK_483(self):
		self._make_stock_entry(serial_no="", qty=1, rate=100, voucher_no="TEST-SN-MISSING")
		columns, data = report_execute({"item_code": self.item.name})
		serials = [row.get("serial_no") for row in data]
		self.assertNotIn("", serials)

	def test_unsubmitted_stock_entry_is_ignored_TC_SCK_484(self):
		serial_no = "SN-UNSUB"
		se = frappe.get_doc(
			{
				"doctype": "Stock Entry",
				"stock_entry_type": "Material Receipt",
				"company": self.company,
				"posting_date": today(),
				"items": [
					{
						"item_code": self.item.name,
						"qty": 1,
						"t_warehouse": self.warehouse,
						"uom": "Nos",
						"conversion_factor": 1,
						"basic_rate": 100,
						"serial_no": serial_no,
					}
				],
			}
		)
		se.insert()
		columns, data = report_execute({"item_code": self.item.name})
		serials = [row.get("serial_no") for row in data]
		self.assertNotIn(serial_no, serials)

	def tearDown(self):
		frappe.db.rollback()
