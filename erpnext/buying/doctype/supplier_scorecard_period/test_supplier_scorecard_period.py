# Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt
import frappe
import unittest


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
				{"criteria_name": supplier_scorecard_criteria.name, "weight": 70},
			]
		})

		with self.assertRaises(frappe.ValidationError) as context:
			doc.validate_criteria_weights()
		self.assertIn("Criteria weights must add up to 100%", str(context.exception))

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

	def test_calculate_score(self):
		doc = frappe.get_doc({
			"doctype": "Supplier Scorecard Period",
			"scorecard": "Test Scorecard", 
			"criteria": [
				{"criteria": "Quality", "weight": 60, "score": 80},
				{"criteria": "Delivery", "weight": 40, "score": 90}
			]
		})

		doc.calculate_score()

		expected_score = (60 * 80 / 100.0) + (40 * 90 / 100.0)
		self.assertEqual(doc.total_score, expected_score)

	def test_calculate_weighted_score(self):
		doc = frappe.get_doc({
        "doctype": "Supplier Scorecard Period",
        "scorecard": "Test Scorecard",
        "from_date": "2024-01-01",
        "to_date": "2024-12-31"
		})

		doc.get_eval_statement = lambda fn: "min(80, 100)"

		result = doc.calculate_weighted_score(doc.get_eval_statement)
		self.assertEqual(result, 80)

	def test_get_eval_statement(self):
		doc = frappe.get_doc({
			"doctype": "Supplier Scorecard Period",
			"variables": [
				frappe._dict({"param_name": "quality", "value": 80}),
				frappe._dict({"param_name": "delivery", "value": None})
			]
		})

		formula = "{quality} * 0.5 + {delivery} * 0.5"
		expected = "80.00 * 0.5 + 0.0 * 0.5"

		result = doc.get_eval_statement(formula)
		self.assertEqual(result, expected)
