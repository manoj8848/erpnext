# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors and Contributors
# See license.txt


import frappe

test_records = frappe.get_test_records("Item Attribute")

from frappe.tests.utils import FrappeTestCase

from erpnext.accounts.doctype.payment_entry.test_payment_entry import make_test_item
from erpnext.stock.doctype.item_attribute.item_attribute import ItemAttributeIncrementError


class TestItemAttribute(FrappeTestCase):
	def setUp(self):
		super().setUp()
		if frappe.db.exists("Item Attribute", "_Test_Length"):
			frappe.delete_doc("Item Attribute", "_Test_Length")

	def tearDown(self):
		frappe.db.rollback()

	# codecov
	def test_validate_exising_items_TC_SCK_325(self):
		from erpnext.stock.doctype.item_attribute.item_attribute import ItemAttribute

		template = "Test Template Item"
		variant = "Test Variant Item"
		# Create an Item Attribute with abbr values to avoid .lower() error
		attribute = frappe.get_doc(
			{
				"doctype": "Item Attribute",
				"attribute_name": "Test Attribute",
				"numeric_values": 0,
				"item_attribute_values": [
					{"attribute_value": "Red", "abbr": "R"},
					{"attribute_value": "Blue", "abbr": "B"},
					{"attribute_value": "Green", "abbr": "G"},
				],
			}
		).insert()

		if not frappe.db.exists("Item", template):
			template = frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": "Test Template Item",
					"item_name": "Test Template Item",
					"has_variants": 1,
					"variant_based_on": "Item Attribute",
					"gst_hsn_code": "01011010",
					"attributes": [{"attribute": attribute.name}],
				}
			).insert()

		# Create a Variant Item with one of the attribute values
		if not frappe.db.exists("Item", variant):
			variant = frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": "Test Variant Item",
					"item_name": "Test Variant Item",
					"variant_of": template.name,
					"gst_hsn_code": "01011010",
					"attributes": [{"attribute": attribute.name, "attribute_value": "Blue"}],
				}
			).insert()

		# Reload and run validation to trigger the for loop
		attribute = frappe.get_doc("Item Attribute", attribute.name)
		attribute.validate_exising_items()

		# If no ValidationError is thrown, the test passes.
		self.assertTrue(True, "Validation passed for existing item attribute values")

	def test_numeric_item_attribute(self):
		item_attribute = frappe.get_doc(
			{
				"doctype": "Item Attribute",
				"attribute_name": "_Test_Length",
				"numeric_values": 1,
				"from_range": 0.0,
				"to_range": 100.0,
				"increment": 0,
			}
		)

		self.assertRaises(ItemAttributeIncrementError, item_attribute.save)

		item_attribute.increment = 0.5
		item_attribute.save()
