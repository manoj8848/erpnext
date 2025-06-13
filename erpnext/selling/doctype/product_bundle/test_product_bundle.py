# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
test_records = frappe.get_test_records("Product Bundle")

class TestProductBundle(FrappeTestCase):
	def test_get_new_item_code_TC_S_193(self):
		from erpnext.selling.doctype.product_bundle.product_bundle import get_new_item_code
		from erpnext.stock.doctype.item.test_item import make_item

		if not frappe.db.exists("Item", "_Unbundled Item"):
			make_item("_Unbundled Item", {"is_stock_item": 0})

		results = get_new_item_code(
			doctype="Item",
			txt="_Unbundled Item",
			searchfield="item_name",
			start=0,
			page_len=10,
			filters={}
		)
		result_codes = [r[0] for r in results]

		self.assertIn("_Unbundled Item", result_codes)
		self.assertNotIn("_Product Bundle Item", result_codes)

def make_product_bundle(parent, items, qty=None):
	if frappe.db.exists("Product Bundle", parent):
		return frappe.get_doc("Product Bundle", parent)

	product_bundle = frappe.get_doc({"doctype": "Product Bundle", "new_item_code": parent})

	for item in items:
		product_bundle.append("items", {"item_code": item, "qty": qty or 1})

	product_bundle.insert()

	return product_bundle
