# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe

from frappe.utils import today, add_days
from frappe.tests.utils import FrappeTestCase

from erpnext.accounts.doctype.payment_entry.test_payment_entry import make_test_item
from erpnext.stock.doctype.material_request.material_request import make_purchase_order
from erpnext.stock.doctype.material_request.test_material_request import make_material_request
from erpnext.buying.doctype.supplier.test_supplier import create_supplier
from erpnext.buying.report.procurement_tracker.procurement_tracker import execute

class TestProcurementTracker(FrappeTestCase):
	def setUp(self):
		self.item = make_test_item("test_procurement_item")
		self.supplier = create_supplier(supplier_name="_Test Supplier Procurement")
		self.filters = frappe._dict(
			from_date = add_days(today(), -30),
			to_date = today(),
		)

	def tearDown(self):
		frappe.db.rollback()

	def test_procurement_tracker_report_TC_B_216(self):
		mr = make_material_request(
			item_code = self.item.item_code,
			do_not_submit = True
		)
		mr.submit()
		self.assertEqual(mr.docstatus, 1)

		po = make_purchase_order(mr.name)
		po.supplier = self.supplier
		po.insert()
		po.submit()
		self.assertEqual(po.docstatus, 1)

		self.filters["company"] = po.company

		data = execute(self.filters)
		for item in data[1]:
			if item.get("item_code") == self.item.item_code:
				self.assertEqual(item.get("item_code"), "test_procurement_item")
				self.assertEqual(item.get("quantity"), 10)
				self.assertEqual(item.get("unit_of_measurement"), "Nos")
				self.assertEqual(item.get("status"), "To Receive and Bill")
				self.assertEqual(item.get("supplier"), "_Test Supplier Procurement")
				self.assertEqual(item.get("estimated_cost"), 0)
				self.assertEqual(item.get("actual_cost"), 0)
				self.assertEqual(item.get("purchase_order_amt"), 0)
				self.assertEqual(item.get("purchase_order_amt_in_company_currency"), 0)