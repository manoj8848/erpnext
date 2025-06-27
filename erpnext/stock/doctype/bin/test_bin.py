# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import nowdate

from erpnext.manufacturing.doctype.production_plan.test_production_plan import make_bom
from erpnext.stock.doctype.bin.bin import on_doctype_update
from erpnext.stock.doctype.item.test_item import make_item
from erpnext.stock.doctype.warehouse.test_warehouse import create_warehouse
from erpnext.stock.utils import _create_bin


class TestBin(FrappeTestCase):
	def test_concurrent_inserts(self):
		"""Ensure no duplicates are possible in case of concurrent inserts"""
		item_code = "_TestConcurrentBin"
		make_item(item_code)
		warehouse = "_Test Warehouse - _TC"

		bin1 = frappe.get_doc(doctype="Bin", item_code=item_code, warehouse=warehouse)
		bin1.insert()

		try:
			bin2 = frappe.get_doc(doctype="Bin", item_code=item_code, warehouse=warehouse)
			bin2.insert()
		except Exception:
			pass

		# util method should handle it
		bin = _create_bin(item_code, warehouse)
		self.assertEqual(bin.item_code, item_code)

		frappe.db.rollback()

	def test_index_exists(self):
		indexes = frappe.db.sql("SELECT * FROM pg_indexes WHERE tablename = 'tabBin'", as_dict=1)
		if not any(index.get("indexname") == "unique_item_warehouse" for index in indexes):
			self.fail("Expected unique index on item-warehouse")

	def test_update_reserved_qty_for_sub_assembly_TC_SCK_466(self):
		item_code = "_TestSubAssemblyItem"
		raw_material_code = "_TestRawMaterial"
		warehouse = create_warehouse("_Test Warehouse")

		# Create items
		make_item(raw_material_code, {"is_stock_item": 1})
		bom_item = make_item(item_code, {"is_sub_contracted_item": 0, "is_stock_item": 1})

		# Create BOM
		bom = make_bom(
			item=item_code, raw_materials=[raw_material_code], rm_qty=2, rate=100, source_warehouse=warehouse
		)

		bom_item.default_bom = bom.name

		# Create Bin
		bin = _create_bin(item_code, warehouse)

		po_items = [{"item_code": item_code, "warehouse": warehouse, "planned_qty": 10, "bom_no": bom.name}]

		# Create Production Plan
		production_plan = frappe.get_doc(
			{
				"doctype": "Production Plan",
				"company": "_Test Company",
				"from_date": nowdate(),
				"to_date": nowdate(),
				"include_exploded_items": 1,
				"po_items": po_items,
			}
		)

		production_plan.insert()
		production_plan.save()
		production_plan.submit()

		# Call the method under test
		bin.update_reserved_qty_for_for_sub_assembly()

		bin.reload()
		self.assertGreaterEqual(bin.reserved_qty_for_production_plan, 0)
		self.assertIsNotNone(bin.projected_qty)

	def test_on_doctype_update_adds_unique_constraint_TC_SCK_467(self):
		# Run the hook
		on_doctype_update()

		# Only run the PostgreSQL-specific check if the DB is PostgreSQL
		if frappe.conf.db_type == "postgres":
			indexes = frappe.db.sql(
				"SELECT indexname FROM pg_indexes WHERE tablename = 'tabBin'", as_dict=True
			)
			index_names = [idx["indexname"] for idx in indexes]
			self.assertIn("unique_item_warehouse", index_names)
		else:
			self.skipTest("PostgreSQL-specific test: skipping on non-Postgres databases.")
