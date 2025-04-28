# Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt


import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.buying.doctype.supplier_scorecard_variable.supplier_scorecard_variable import (
	VariablePathNotFound,
)

from .supplier_scorecard_variable import (
    get_total_workdays,
	get_item_workdays,
	get_total_cost_of_shipments,
	get_cost_of_delayed_shipments,
	get_cost_of_on_time_shipments,
	get_total_days_late,
	get_on_time_shipments,
	get_late_shipments,
	get_total_received,
	get_total_received_amount,
	get_total_received_items,
	get_total_rejected_amount,
	get_total_rejected_items,
	get_total_accepted_amount,
	get_total_accepted_items,
	get_total_shipments,
	get_ordered_qty,
	get_rfq_total_number,
	get_rfq_total_items,
	get_sq_total_number,
	get_sq_total_items,
	get_rfq_response_days
)

class TestSupplierScorecardVariable(FrappeTestCase):
	def tearDown(self):
		return frappe.db.rollback()

	def test_variable_exist(self):
		for d in test_existing_variables:
			my_doc = frappe.get_doc("Supplier Scorecard Variable", d.get("name"))
			self.assertEqual(my_doc.param_name, d.get("param_name"))
			self.assertEqual(my_doc.variable_label, d.get("variable_label"))
			self.assertEqual(my_doc.path, d.get("path"))

	def test_path_exists(self):
		for d in test_good_variables:
			if frappe.db.exists(d):
				frappe.delete_doc(d.get("doctype"), d.get("name"))
			frappe.get_doc(d).insert()

		for d in test_bad_variables:
			self.assertRaises(VariablePathNotFound, frappe.get_doc(d).insert)

	def test_validate_path_exists_code_coverage(self):
		create_ssv = frappe.get_doc(
			{
				"doctype": "Supplier Scorecard Variable",
				"variable_label": "test" + frappe.generate_hash(length=5),
				"param_name": "test_param",
				"path": "frappe.utils.add_days",
				"description": "test_description"
			}
		)
		create_ssv.insert()

		create_ssv.load_from_db()
		create_ssv.path = "frappe.utils.add_days."
		self.assertRaises(VariablePathNotFound, create_ssv.save)

		create_ssv.load_from_db()
		create_ssv.path = "get_total_accepted_items_"
		self.assertRaises(VariablePathNotFound, create_ssv.save)

	def test_get_total_workdays_codecoverage(self):
		supplier_scorecard = setup_supplier_scorecard("_Test Supplier")
		get_sscp = frappe.get_doc("Supplier Scorecard Period", {"supplier": "_Test Supplier"})
		self.assertEqual(get_sscp.docstatus, 1)

		get_total = get_total_workdays(get_sscp)
		self.assertEqual(get_total, 7)

	def test_get_item_workdays_code_coverage(self):
		supplier_scorecard = setup_supplier_scorecard("_Test Supplier")
		get_sscp = frappe.get_doc("Supplier Scorecard Period", {"supplier": "_Test Supplier"})
		get_total = get_item_workdays(get_sscp)
		self.assertEqual(get_sscp.docstatus, 1)

	def test_get_total_cost_of_shipments_code_coverage(self):
		supplier_scorecard = setup_supplier_scorecard("_Test Supplier")
		get_sscp = frappe.get_doc("Supplier Scorecard Period", {"supplier": "_Test Supplier"})
		get_total_cost = get_total_cost_of_shipments(get_sscp)
		self.assertEqual(get_sscp.docstatus, 1)

	def test_get_cost_of_delayed_shipments_code_coverage(self):
		supplier_scorecard = setup_supplier_scorecard("_Test Supplier")
		get_sscp = frappe.get_doc("Supplier Scorecard Period", {"supplier": "_Test Supplier"})
		self.assertEqual(get_sscp.docstatus, 1)
		get_cost = get_cost_of_delayed_shipments(get_sscp)

	def test_get_cost_of_on_time_shipments_code_coverage(self):
		supplier_scorecard = setup_supplier_scorecard("_Test Supplier")
		get_sscp = frappe.get_doc("Supplier Scorecard Period", {"supplier": "_Test Supplier"})
		self.assertEqual(get_sscp.docstatus, 1)
		cost_of_on_time = get_cost_of_on_time_shipments(get_sscp)

	def test_get_total_days_late_code_coverage(self):
		supplier_scorecard = setup_supplier_scorecard("_Test Supplier")
		get_sscp = frappe.get_doc("Supplier Scorecard Period", {"supplier": "_Test Supplier"})
		self.assertEqual(get_sscp.docstatus, 1)
		total_days_late = get_total_days_late(get_sscp)

	def test_get_on_time_shipments_code_coverage(self):
		supplier_scorecard = setup_supplier_scorecard("_Test Supplier")
		get_sscp = frappe.get_doc("Supplier Scorecard Period", {"supplier": "_Test Supplier"})
		self.assertEqual(get_sscp.docstatus, 1)
		time_shipments = get_on_time_shipments(get_sscp)

	def test_get_late_shipments_code_coverage(self):
		supplier_scorecard = setup_supplier_scorecard("_Test Supplier")
		get_sscp = frappe.get_doc("Supplier Scorecard Period", {"supplier": "_Test Supplier"})
		self.assertEqual(get_sscp.docstatus, 1)
		late_shipments = get_late_shipments(get_sscp)

	def test_get_total_received_code_coverage(self):
		supplier_scorecard = setup_supplier_scorecard("_Test Supplier")
		get_sscp = frappe.get_doc("Supplier Scorecard Period", {"supplier": "_Test Supplier"})
		self.assertEqual(get_sscp.docstatus, 1)
		total_received = get_total_received(get_sscp)

	def test_get_total_received_amount_code_coverage(self):
		supplier_scorecard = setup_supplier_scorecard("_Test Supplier")
		get_sscp = frappe.get_doc("Supplier Scorecard Period", {"supplier": "_Test Supplier"})
		self.assertEqual(get_sscp.docstatus, 1)
		total_received_amount = get_total_received_amount(get_sscp)

	def test_get_total_received_items_code_coverage(self):
		supplier_scorecard = setup_supplier_scorecard("_Test Supplier")
		get_sscp = frappe.get_doc("Supplier Scorecard Period", {"supplier": "_Test Supplier"})
		self.assertEqual(get_sscp.docstatus, 1)
		total_received = get_total_received_items(get_sscp)

	def test_get_total_rejected_amount_code_coverage(self):
		supplier_scorecard = setup_supplier_scorecard("_Test Supplier")
		get_sscp = frappe.get_doc("Supplier Scorecard Period", {"supplier": "_Test Supplier"})
		self.assertEqual(get_sscp.docstatus, 1)
		total_rejected = get_total_rejected_amount(get_sscp)

	def test_get_total_rejected_items_code_coverage(self):
		supplier_scorecard = setup_supplier_scorecard("_Test Supplier")
		get_sscp = frappe.get_doc("Supplier Scorecard Period", {"supplier": "_Test Supplier"})
		self.assertEqual(get_sscp.docstatus, 1)
		get_total_rejected = get_total_rejected_items(get_sscp)
		get_total_accepted_amount(get_sscp)
		get_total_accepted_items(get_sscp)
		get_total_shipments(get_sscp)
		get_ordered_qty(get_sscp)
		get_rfq_total_number(get_sscp)
		get_rfq_total_items(get_sscp)
		get_sq_total_number(get_sscp)
		get_sq_total_items(get_sscp)
		get_rfq_response_days(get_sscp)



def setup_supplier_scorecard(supplier_name):

	criteria_name = frappe.get_doc(
		{
			"doctype": "Supplier Scorecard Criteria",
			"criteria_name": "test supplier cretiria",
			"max_score": 100,
			"formula": "10",
		}
	).insert(ignore_permissions=True)

	if not frappe.db.exists("Supplier Scorecard", supplier_name):
		supplier_scorecard = frappe.get_doc({
			"doctype": "Supplier Scorecard",
			"supplier": supplier_name,
			"period": "Per Week",
			"standings": [
				{
					"standing_name": "Very Poor",
					"standing_color": "Red",
					"min_grade": 0.00,
					"max_grade": 100.00,
				}
			],
			"criteria": [
				{
					"criteria_name": criteria_name.name,
					"weight": 100
				}
			]
		}).insert(ignore_permissions=True)

	return {
		"supplier_scorecard": supplier_scorecard
	}


test_existing_variables = [
	{
		"param_name": "total_accepted_items",
		"name": "Total Accepted Items",
		"doctype": "Supplier Scorecard Variable",
		"variable_label": "Total Accepted Items",
		"path": "get_total_accepted_items",
	},
]

test_good_variables = [
	{
		"param_name": "good_variable1",
		"name": "Good Variable 1",
		"doctype": "Supplier Scorecard Variable",
		"variable_label": "Good Variable 1",
		"path": "get_total_accepted_items",
	},
]

test_bad_variables = [
	{
		"param_name": "fake_variable1",
		"name": "Fake Variable 1",
		"doctype": "Supplier Scorecard Variable",
		"variable_label": "Fake Variable 1",
		"path": "get_fake_variable1",
	},
]
