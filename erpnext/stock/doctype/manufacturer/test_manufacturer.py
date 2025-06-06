# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt
import unittest

import frappe

# test_records = frappe.get_test_records('Manufacturer')


class TestManufacturer(unittest.TestCase):
	def tearDown(self):
		frappe.db.rollback()

	# codecov
	def test_onload_TC_SCK_315(self):
		manufacturer_doc = frappe.get_doc(
			{
				"doctype": "Manufacturer",
				"short_name": "Test Item Manufacturer",
				"full_name": "Test Item manufacturer",
				"country": "India",
			}
		).insert()
		manufacturer_doc.onload()
		assert hasattr(manufacturer_doc, "__onload"), "__onload should be set after onload()"
