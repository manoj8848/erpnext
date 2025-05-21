import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today, add_days

from erpnext.subcontracting.doctype.subcontracting_order.test_subcontracting_order import create_subcontracting_order
from erpnext.controllers.tests.test_subcontracting_controller import (
	make_bom_for_subcontracted_items,
	make_raw_materials,
	make_service_items,
	make_subcontracted_items,
)

class TestSubcontractOrderSummery(FrappeTestCase):
	def setUp(self):
		make_subcontracted_items()
		make_raw_materials()
		make_service_items()
		make_bom_for_subcontracted_items()
		self.setup_for_subcontracting_order()

		self.filters = frappe._dict(
			company="_Test Company",
			from_date=add_days(today(), -30),
			to_date=today(),
			order_type="Subcontracting Order"
		)

	def tearDown(self):
		frappe.db.rollback()

	def test_subcontract_order_summary_TC_B_223(self):
		from .subcontract_order_summary import execute
		data = execute(self.filters)
		for row in data[1]:
			if row.get("item_code") == "Subcontracted Item SA8":
				self.assertEqual(row.get("item_name"), "Subcontracted Item SA8")
				self.assertEqual(row.get("qty"), 10)
				self.assertEqual(row.get("received_qty"), 0)
				self.assertEqual(row.get("status"), "Open")
				self.assertEqual(row.get("main_item_code"), "Subcontracted Item SA8")
				self.assertEqual(row.get("rm_item_code"), "Subcontracted SRM Item 8")
				self.assertEqual(row.get("required_qty"), 10)
				self.assertEqual(row.get("supplied_qty"), 0)
				self.assertEqual(row.get("returned_qty"), 0)
				self.assertEqual(row.get("total_supplied_qty"), 0)
				self.assertEqual(row.get("consumed_qty"), 0)

	def setup_for_subcontracting_order(self):
		from erpnext.stock.doctype.material_request.material_request import make_purchase_order
		from erpnext.stock.doctype.material_request.test_material_request import make_material_request

		mr = make_material_request(
			item_code="Subcontracted Item SA8",
			material_request_type="Purchase",
			qty=10,
		)

		self.assertTrue(mr.docstatus == 1)

		po = make_purchase_order(mr.name)
		po.is_subcontracted = 1
		po.supplier = "_Test Supplier"
		po.items[0].fg_item = "Subcontracted Item SA8"
		po.items[0].fg_item_qty = 10
		po.items[0].item_code = "Subcontracted Service Item 8"
		po.items[0].item_name = "Subcontracted Service Item 8"
		po.items[0].qty = 10
		po.supplier_warehouse = "_Test Warehouse 1 - _TC"
		po.save()
		po.submit()

		self.assertTrue(po.items[0].material_request)
		self.assertTrue(po.items[0].material_request_item)

		sco = create_subcontracting_order(po_name=po.name)
		self.assertTrue(sco.items[0].material_request)
		self.assertTrue(sco.items[0].material_request_item)