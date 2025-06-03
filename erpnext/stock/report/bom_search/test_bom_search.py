import frappe
import unittest
from erpnext.stock.doctype.item.test_item import create_item
from frappe import _dict

class TestBOMSearchReport(unittest.TestCase):
	def setUp(self):
		self.item = create_item("_Test Item BOM Search", {"stock_uom": "Nos", "is_stock_item": 1})

		self.bom = frappe.get_doc({
			"doctype": "BOM",
			"item": self.item.name,
			"quantity": 1,
			"is_active": 1,
			"is_default": 1,
			"items": [{
				"item_code": self.item.name,
				"qty": 1
			}]
		}).insert(ignore_permissions=True)

	def tearDown(self):
		frappe.delete_doc("BOM", self.bom.name, force=True)
		frappe.delete_doc("Item", self.item.name, force=True)

	def test_bom_search_without_sub_assemblies(self):
		from erpnext.stock.report.bom_search import bom_search
		columns, data = bom_search.execute(filters=_dict({"_Test BOM Search Item": self.item.name}))

		found = any(row[0] == self.bom.name for row in data)
		self.assertTrue(found)

	def test_bom_search_with_sub_assemblies(self):
		from erpnext.stock.report.bom_search import bom_search
		columns, data = bom_search.execute(filters=_dict({"_Test BOM Search Item": self.item.name, "search_sub_assemblies": 1}))

		found = any(d[0] == self.bom.name for d in data)
		self.assertTrue(found)
