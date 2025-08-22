import unittest

import frappe
from frappe import _dict
from frappe.tests.utils import FrappeTestCase

from erpnext.stock.doctype.item.test_item import create_item
from erpnext.stock.doctype.stock_entry.test_stock_entry import make_stock_entry
from erpnext.stock.report.warehouse_wise_stock_balance import warehouse_wise_stock_balance


class TestWarehouseStockBalanceReport(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.company = "_Test Company"

		self.parent_wh = create_warehouse("_Test Main Warehouse", is_group=1)
		self.child_wh1 = create_warehouse("_Test WH A", parent_warehouse=self.parent_wh.name)
		self.child_wh2 = create_warehouse("_Test WH B", parent_warehouse=self.parent_wh.name)
		self.disabled_wh = create_warehouse("_Test WH Disabled", disabled=1)

		self.item = create_item("_Test Item", {"is_stock_item": 1, "stock_uom": "Nos"})

		make_stock_entry(
			item_code=self.item.name,
			target=self.child_wh1.name,
			qty=10,
			basic_rate=10,  # total = 100
			to_warehouse=self.child_wh1.name,
			company=self.company,
			purpose="Material Receipt",
		)

		make_stock_entry(
			item_code=self.item.name,
			target=self.child_wh2.name,
			qty=5,
			basic_rate=10,  # total = 50
			to_warehouse=self.child_wh2.name,
			company=self.company,
			purpose="Material Receipt",
		)

	def test_basic_report_output_T_WWSB_001(self):
		filters = _dict(company=self.company, warehouse=None, show_disabled_warehouses=None)
		columns, data = warehouse_wise_stock_balance.execute(filters)

		wh_names = [d.name for d in data]
		self.assertIn(self.child_wh1.name, wh_names)
		self.assertIn(self.child_wh2.name, wh_names)

	def test_aggregation_of_stock_balance_T_WWSB_002(self):
		filters = _dict(company=self.company)
		_, data = warehouse_wise_stock_balance.execute(filters)

		wh_data = {d.name: d.stock_balance for d in data}
		self.assertEqual(wh_data[self.child_wh1.name], 100)
		self.assertEqual(wh_data[self.child_wh2.name], 50)

	def test_show_disabled_warehouses_T_WWSB_003(self):
		filters = _dict(company=self.company, show_disabled_warehouses=1)
		columns, data = warehouse_wise_stock_balance.execute(filters)

		self.assertIn("disabled", [col["fieldname"] for col in columns])
		disabled_warehouses = [d for d in data if d.get("disabled")]
		self.assertTrue(any(w.name == self.disabled_wh.name for w in disabled_warehouses))

	def test_balance_propagation_to_parent_T_WWSB_004(self):
		filters = _dict(company=self.company)
		_, data = warehouse_wise_stock_balance.execute(filters)

		main_wh = next(d for d in data if d.name == self.parent_wh.name)
		self.assertEqual(main_wh.stock_balance, 150)

	def test_indent_hierarchy_T_WWSB_005(self):
		filters = _dict(company=self.company)
		_, data = warehouse_wise_stock_balance.execute(filters)

		indent_map = {d.name: d.get("indent", 0) for d in data}
		self.assertGreater(indent_map[self.child_wh1.name], indent_map[self.parent_wh.name])


def create_warehouse(name, is_group=False, parent_warehouse=None, disabled=0):
	return frappe.get_doc(
		{
			"doctype": "Warehouse",
			"warehouse_name": name,
			"is_group": is_group,
			"parent_warehouse": parent_warehouse,
			"disabled": disabled,
			"company": "_Test Company",
		}
	).insert()
