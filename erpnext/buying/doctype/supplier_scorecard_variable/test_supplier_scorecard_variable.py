# Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt


import frappe
from frappe.tests.utils import FrappeTestCase

from frappe.utils import today, add_days

from erpnext.buying.doctype.supplier_scorecard_variable.supplier_scorecard_variable import (
	VariablePathNotFound,
)
from erpnext.buying.doctype.supplier.test_supplier import create_supplier

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

	def test_validate_path_exists_TC_B_172(self):
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

	def test_get_total_workdays_TC_B_173(self):
		get_sscp = score_card()
		get_sscp.submit()
		self.assertEqual(get_sscp.docstatus, 1)

		get_total = get_total_workdays(get_sscp)
		self.assertEqual(get_total, 7)

	def test_get_item_workdays_TC_B_174(self):
		get_sscp = score_card()
		get_sscp.submit()
		self.assertEqual(get_sscp.docstatus, 1)

		get_total = get_item_workdays(get_sscp)
		self.assertEqual(get_total, 0)

		get_total_cost = get_total_cost_of_shipments(get_sscp)
		self.assertEqual(get_total_cost, 0)

		get_cost_delayed = get_cost_of_delayed_shipments(get_sscp)
		self.assertEqual(get_cost_delayed, 0)

		cost_of_on_time = get_cost_of_on_time_shipments(get_sscp)
		self.assertEqual(cost_of_on_time, 0)

		total_days_late = get_total_days_late(get_sscp)
		self.assertEqual(total_days_late, 0)

		time_shipments = get_on_time_shipments(get_sscp)
		self.assertEqual(time_shipments, 0)

		late_shipments = get_late_shipments(get_sscp)
		self.assertEqual(late_shipments, 0)

		total_received = get_total_received(get_sscp)
		self.assertEqual(total_received, 0)

		total_received_amount = get_total_received_amount(get_sscp)
		self.assertEqual(total_received_amount, 0)

		total_received_items = get_total_received_items(get_sscp)
		self.assertEqual(total_received_items, 0)

		total_rejected = get_total_rejected_amount(get_sscp)
		self.assertEqual(total_rejected, 0)

		get_total_rejected = get_total_rejected_items(get_sscp)
		self.assertEqual(get_total_rejected, 0)

		total_accepted_amount = get_total_accepted_amount(get_sscp)
		self.assertEqual(total_accepted_amount, 0)

		total_accepted_items = get_total_accepted_items(get_sscp)
		self.assertEqual(total_accepted_items, 0)

		total_shipments = get_total_shipments(get_sscp)
		self.assertEqual(total_shipments, 0)

		ordered_qty = get_ordered_qty(get_sscp)
		self.assertEqual(ordered_qty, 0)

		rfq_totals = get_rfq_total_number(get_sscp)
		self.assertEqual(rfq_totals, 0)

		rfq_total_items = get_rfq_total_items(get_sscp)
		self.assertEqual(rfq_total_items, 0)

		sg_total_num = get_sq_total_number(get_sscp)
		self.assertEqual(sg_total_num, 0)

		sg_totla_items = get_sq_total_items(get_sscp)
		self.assertEqual(sg_totla_items, 0)

		rfq_response = get_rfq_response_days(get_sscp)
		self.assertEqual(rfq_response, 0)

def score_card():
	supplier = create_supplier(supplier_name="__test_supplier" + frappe.generate_hash(length=5))
	ssc = setup_supplier_scorecard(supplier.name)
	sscp = frappe.get_doc(
		{
			"doctype": "Supplier Scorecard Period",
			"supplier": supplier.name,
			"total_score": 5,
			"start_date": today(),
			"end_date": add_days(today(), 7),
			"scorecard": supplier.name,
			"criteria": [
				{
					"criteria_name": ssc.get("criteria_name"),
					"weight": 100,
					"formula": "10"
				}
			]
		}
	)
	sscp.insert(ignore_permissions=True)

	return sscp

def setup_supplier_scorecard(supplier_name):

	criteria_name = frappe.get_doc(
		{
			"doctype": "Supplier Scorecard Criteria",
			"criteria_name": "test supplier cretiria" + frappe.generate_hash(length=4),
			"max_score": 100,
			"formula": "10",
		}
	).insert(ignore_permissions=True, ignore_if_duplicate=True).name

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
					"criteria_name": criteria_name,
					"weight": 100
				}
			]
		}).insert(ignore_permissions=True)

	return {
		"supplier_scorecard": frappe.db.get_value("Supplier Scorecard", {"supplier": supplier_name}),
		"criteria_name": criteria_name
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
