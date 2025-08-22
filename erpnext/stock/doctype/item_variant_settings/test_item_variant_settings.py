# Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt
import unittest

import frappe

from erpnext.accounts.doctype.payment_entry.test_payment_entry import make_test_item


class TestItemVariantSettings(unittest.TestCase):
	def tearDown(self):
		frappe.db.rollback()

	# codecov
	def test_remove_invalid_fields_for_copy_fields_in_variants_TC_SCK_321(self):
		variant_doc = frappe.get_doc(
			{
				"doctype": "Item Variant Settings",
				"invalid_fields_for_copy_fields_in_variants": ["field_b"],
				"fields": [{"field_name": "field_a"}, {"field_name": "field_b"}, {"field_name": "field_c"}],
			}
		)
		self.assertRaises(
			frappe.ValidationError,
			variant_doc.insert,
			"Expected ValidationError when inserting variant_doc with invalid field 'field_b'",
		)

	# codecov
	def test_remove_invalid_fields_for_copy_fields_in_variants_TC_SCK_322(self):
		variant_doc = frappe.get_doc(
			{
				"doctype": "Item Variant Settings",
				"invalid_fields_for_copy_fields_in_variants": ["field_b"],
				"fields": [
					{"field_name": "field_a_variant1"},
					{"field_name": "field_b_variant2"},
					{"field_name": "field_c_variant3"},
				],
			}
		).insert()
		variant_doc.remove_invalid_fields_for_copy_fields_in_variants()
		remaining_field_names = [f.field_name for f in variant_doc.fields]

		# Assert the invalid field is removed
		self.assertNotIn("field_b", remaining_field_names)

		# Assert the valid fields remain
		self.assertIn("field_a_variant1", remaining_field_names)
		self.assertIn("field_c_variant3", remaining_field_names)
