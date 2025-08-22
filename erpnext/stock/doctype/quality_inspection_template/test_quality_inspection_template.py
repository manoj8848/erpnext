# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt
import unittest

import frappe

from erpnext.stock.doctype.quality_inspection_template.quality_inspection_template import get_template_details


class TestQualityInspectionTemplate(unittest.TestCase):
	def teardown(self):
		frappe.db.rollback()

	# codecov
	def test_get_template_details_TC_SCK_323(self):
		result = get_template_details(None)
		# Assert that the result is an empty list as no template
		self.assertEqual(result, [])
