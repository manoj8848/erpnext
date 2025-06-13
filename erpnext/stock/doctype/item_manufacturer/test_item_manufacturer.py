# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import unittest

import frappe

from erpnext.accounts.doctype.payment_entry.test_payment_entry import make_test_item


class TestItemManufacturer(unittest.TestCase):
	def tearDown(self):
		frappe.db.rollback()

	# codecov
	def test_validate_TC_SCK_313(self):
		from erpnext.stock.doctype.item_manufacturer.item_manufacturer import get_item_manufacturer_part_no

		item_code = "_Test Item"

		manufacturer_doc = frappe.get_doc(
			{
				"doctype": "Manufacturer",
				"short_name": "Test Item Manufacturer",
				"full_name": "Test Item manufacturer",
				"country": "India",
			}
		).insert()

		item_create = make_test_item(item_code)
		item_create.default_item_manufacturer = manufacturer_doc.name
		item_create.default_manufacturer_part_no = "001"
		item_create.save()

		item_manufacturer_doc = frappe.get_doc(
			{
				"doctype": "Item Manufacturer",
				"item_code": item_code,
				"manufacturer": manufacturer_doc,
				"manufacturer_part_no": "001",
			}
		).insert()
		get_item_manufacturer_part_no(item_code, manufacturer_doc.name)
		self.assertEqual(item_manufacturer_doc.item_code, item_code)
		self.assertEqual(item_manufacturer_doc.manufacturer, manufacturer_doc.name)
		self.assertEqual(item_manufacturer_doc.manufacturer_part_no, "001")

	# codecov
	def test_validate_delete_TC_SCK_314(self):
		item_code = "_Test Item"

		manufacturer_doc = frappe.get_doc(
			{
				"doctype": "Manufacturer",
				"short_name": "Test Item Manufacturer",
				"full_name": "Test Item manufacturer",
				"country": "India",
			}
		).insert()

		item_create = make_test_item(item_code)
		item_create.default_item_manufacturer = manufacturer_doc.name
		item_create.default_manufacturer_part_no = "001"
		item_create.save()

		item_manufacturer_doc = frappe.get_doc(
			{
				"doctype": "Item Manufacturer",
				"item_code": item_code,
				"is_default": 1,
				"manufacturer": manufacturer_doc.name,
				"manufacturer_part_no": "001",
			}
		).insert()
		item_manufacturer_doc.reload()
		item_manufacturer_doc.delete()
		item = frappe.get_doc("Item", item_code)
		self.assertIsNone(item.default_item_manufacturer)
		self.assertIsNone(item.default_manufacturer_part_no)
