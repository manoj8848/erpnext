# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

test_records = frappe.get_test_records("Sales Taxes and Charges Template")


class TestSalesTaxesandChargesTemplate(FrappeTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_sales_taxes_TC_ACC_227(self):
		template = "_Test Sales Taxes And Charges Template_1122"
		if not frappe.db.exists("Sales Taxes and Charges Template", template):
			doc = frappe.copy_doc(test_records[0])
			doc.title = template
			doc.taxes[0].rate = 0.0
			doc.insert(ignore_permissions=True)
			doc.set_missing_values()
			self.assertEqual(doc.company, "_Test Company")
			self.assertEqual(doc.taxes[0].account_head, "_Test Account VAT - _TC")
			self.assertEqual(doc.taxes[1].account_head, "_Test Account Service Tax - _TC")

	def test_validate_disabled_template_TC_ACC_228(self):
		tax_template = frappe.copy_doc(test_records[0])
		tax_template.title = "__Test Validate Disabled Template_"
		tax_template.is_default = 1
		tax_template.disabled = 1

		with self.assertRaises(frappe.ValidationError) as cm:
			tax_template.insert(ignore_permissions=True)
		self.assertIn("Disabled template must not be default template", str(cm.exception))
