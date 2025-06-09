import unittest

import frappe


class TestAccountsSettings(unittest.TestCase):
	def tearDown(self):
		# Just in case `save` method succeeds, we need to take things back to default so that other tests
		# don't break
		cur_settings = frappe.get_doc("Accounts Settings", "Accounts Settings")
		cur_settings.allow_stale = 1
		cur_settings.save()

	def test_stale_days(self):
		cur_settings = frappe.get_doc("Accounts Settings", "Accounts Settings")
		cur_settings.allow_stale = 0
		cur_settings.stale_days = 0

		self.assertRaises(frappe.ValidationError, cur_settings.save)

		cur_settings.stale_days = -1
		self.assertRaises(frappe.ValidationError, cur_settings.save)

	def test_enable_payment_schedule_in_print_method(self):
		from unittest.mock import patch

		from erpnext.accounts.doctype.account.test_account import create_account

		self.accounts_settings = frappe.get_doc("Accounts Settings", "Accounts Settings")
		self.accounts_settings.show_payment_schedule_in_print = 1

		# Create test document
		settings = frappe.new_doc("Accounts Settings")
		settings.show_payment_schedule_in_print = 1

		# Manually set _doc_before_save to simulate previous state
		settings._doc_before_save = frappe._dict(
			{
				"show_payment_schedule_in_print": 0,
				"add_taxes_from_item_tax_template": 0,
				"enable_common_party_accounting": 0,
				"acc_frozen_upto": None,
			}
		)

		# Mock the enable method
		with patch.object(settings, "enable_payment_schedule_in_print") as mock_method:
			settings.validate()
			mock_method.assert_called_once()
		settings.enable_payment_schedule_in_print()
		self.assertEqual(self.accounts_settings.show_payment_schedule_in_print, 1)
