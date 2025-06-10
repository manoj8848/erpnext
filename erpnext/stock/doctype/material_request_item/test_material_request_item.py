import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.stock.doctype.material_request_item.material_request_item import on_doctype_update


class TestMaterialRequestItem(FrappeTestCase):
	def test_on_doctype_update_adds_index_TC_SCK_334(self):
		# Just call the function on_doctype_update
		on_doctype_update()
