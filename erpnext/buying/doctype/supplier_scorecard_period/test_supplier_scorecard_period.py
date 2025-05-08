# Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import unittest
import frappe


class TestSupplierScorecardPeriod(unittest.TestCase):
	def test_import_string_path(self):
		from erpnext.buying.doctype.supplier_scorecard_period.supplier_scorecard_period import import_string_path
		from frappe.utils import add_days

		self.assertEqual(import_string_path("frappe.utils.add_days"), add_days)
		self.assertRaises(AttributeError, import_string_path, "frappe.utils.invalid_func")

	def test_validate_criteria_weights(self):
		supplier_scorecard_criteria = frappe.get_doc(
			{
				"doctype": "Supplier Scorecard Criteria",
				"max_score": "100",
				"formula": "max(0,10)*100",
				"criteria_name": "_Test Criteria"
			}
		).insert(ignore_permissions=True, ignore_if_duplicate=True)
		supplier_doc = frappe.get_doc(
			{
				"doctype": "Supplier",
				"supplier_name": "Test Supplier for RFQ",
			}
		).insert(ignore_permissions=True, ignore_if_duplicate=True)
		supplier_scorecard = frappe.get_doc(
			{
				"doctype": "Supplier Scorecard",
				"supplier": supplier_doc.name,
				"period": "Per Month",
				"criteria": [{'criteria_name': supplier_scorecard_criteria.name, "weight": 100}],
				"standings": [
					{"min_grade": 0, "max_grade": 49, "standing": "Poor"},
					{"min_grade": 49, "max_grade": 74, "standing": "Average"},
					{"min_grade": 74, "max_grade": 100, "standing": "Excellent"},
				]
			}
		).insert(ignore_permissions=True, ignore_if_duplicate=True)
		doc = frappe.get_doc({
			"doctype": "Supplier Scorecard Period",
			"scorecard": supplier_scorecard.name,
			"from_date": "2024-01-01",
			"to_date": "2024-12-31",
			"criteria": [
				{"criteria_name": supplier_scorecard_criteria.name, "weight": 100},
			]
		})
		# Should pass without error
		doc.validate_criteria_weights()

		# Modify to invalid weights
		doc.criteria[0].weight = 70
		with self.assertRaises(frappe.ValidationError):
			doc.validate_criteria_weights()

	def test_calculate_variables(self):
		supplier_scorecard_criteria = frappe.get_doc(
			{
				"doctype": "Supplier Scorecard Criteria",
				"max_score": "100",
				"formula": "max(0,10)*100",
				"criteria_name": "_Test Criteria"
			}
		).insert(ignore_permissions=True, ignore_if_duplicate=True)
		supplier_doc = frappe.get_doc(
			{
				"doctype": "Supplier",
				"supplier_name": "Test Supplier for RFQ",
			}
		).insert(ignore_permissions=True, ignore_if_duplicate=True)
		supplier_scorecard = frappe.get_doc(
			{
				"doctype": "Supplier Scorecard",
				"supplier": supplier_doc.name,
				"period": "Per Month",
				"criteria": [{'criteria_name': supplier_scorecard_criteria.name, "weight": 100}],
				"standings": [
					{"min_grade": 0, "max_grade": 49, "standing": "Poor"},
					{"min_grade": 49, "max_grade": 74, "standing": "Average"},
					{"min_grade": 74, "max_grade": 100, "standing": "Excellent"},
				]
			}
		).insert(ignore_permissions=True, ignore_if_duplicate=True)
		supplier_scorecard_variable = frappe.get_doc(
			{
				"doctype": "Supplier Scorecard Variable",
				"variable_label": "Test",
				"param_name": "Test",
				"path": "get_ordered_qty"
			}
		).insert(ignore_permissions=True, ignore_if_duplicate=True)
		doc = frappe.get_doc({
			"doctype": "Supplier Scorecard Period",
			"scorecard": supplier_scorecard.name,
			"from_date": "2024-01-01",
			"to_date": "2024-12-31",
			"criteria": [
				{"criteria_name": supplier_scorecard_criteria.name, "weight": 100},
			],
			"variables": [
				{
					"variable_label": supplier_scorecard_variable.name,
					"path": "get_ordered_qty"
				}
			]
		})

		doc.calculate_variables()

		self.assertIsNotNone(doc.variables[0].value)