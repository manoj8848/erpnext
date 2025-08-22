# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import unittest

import frappe


class TestSellingSettings(unittest.TestCase):
	def test_defaults_populated(self):
		# Setup default values are not populated on migrate, this test checks
		# if setup was completed correctly
		default = frappe.db.get_single_value("Selling Settings", "maintain_same_rate_action")
		self.assertEqual("Stop", default)

	def test_toggle_discount_accounting_fields_coverage_TC_S_187(self):
		
		selling_setting = frappe.new_doc("Selling Settings")
		selling_setting.enable_discount_accounting = 1
		selling_setting.save()
		selling_setting.toggle_discount_accounting_fields()
  
		self.assertEqual(selling_setting.enable_discount_accounting, 1)