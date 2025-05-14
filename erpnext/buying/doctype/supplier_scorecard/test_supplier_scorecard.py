# Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt


import frappe
from frappe.utils import add_days, now
from frappe.tests.utils import FrappeTestCase

from erpnext.buying.doctype.supplier.test_supplier import create_supplier
from erpnext.buying.doctype.supplier_scorecard_variable.test_supplier_scorecard_variable import score_card
from erpnext.buying.doctype.supplier_scorecard.supplier_scorecard import get_timeline_data, refresh_scorecards

class TestSupplierScorecard(FrappeTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_create_scorecard(self):
		doc = make_supplier_scorecard().insert()
		self.assertEqual(doc.name, valid_scorecard[0].get("supplier"))

	def test_criteria_weight(self):
		delete_test_scorecards()
		my_doc = make_supplier_scorecard()
		for d in my_doc.criteria:
			d.weight = 0
		self.assertRaises(frappe.ValidationError, my_doc.insert)

	def test_validate_overlap_standings_TC_B_190(self):
		my_doc = setup_supplier_scorecard()
		my_doc.load_from_db()
		my_doc.standings[0].max_grade = 40.0
		self.assertRaises(frappe.ValidationError, my_doc.save)

	def test_validata_statnding_TC_B_191(self):
		my_doc = setup_supplier_scorecard()
		my_doc.load_from_db()
		my_doc.standings = ""
		self.assertRaises(frappe.ValidationError, my_doc.save)

	def test_timeline_data_TC_B_192(self):
		sscp = score_card()
		sscp.submit()
		get_data = get_timeline_data("Supplier Scorecard", sscp.scorecard)
		refresh_scorecards()
		self.assertEqual(sscp.docstatus, 1)

def setup_supplier_scorecard():
	supplier = create_supplier(supplier_name="__test_supplier" + frappe.generate_hash(length=5))
	frappe.db.set_value("Supplier", supplier.name, "creation", add_days(now(), -10))
	criteria_name = frappe.get_doc(
		{
			"doctype": "Supplier Scorecard Criteria",
			"criteria_name": "test supplier cretiria" + frappe.generate_hash(length=4),
			"max_score": 100,
			"formula": "10",
		}
	).insert(ignore_permissions=True, ignore_if_duplicate=True).name

	if not frappe.db.exists("Supplier Scorecard", supplier.name):
		supplier_scorecard = frappe.get_doc({
			"doctype": "Supplier Scorecard",
			"supplier": supplier.name,
			"period": "Per Week",
			"standings": valid_scorecard[0].get("standings"),
			"criteria": [
				{
					"criteria_name": criteria_name,
					"weight": 100
				}
			]
		}).insert(ignore_permissions=True)

	doc = frappe.get_doc("Supplier Scorecard", {"supplier": supplier.name})

	return  doc

def make_supplier_scorecard():
	my_doc = frappe.get_doc(valid_scorecard[0])

	# Make sure the criteria exist (making them)
	for d in valid_scorecard[0].get("criteria"):
		if not frappe.db.exists("Supplier Scorecard Criteria", d.get("criteria_name")):
			d["doctype"] = "Supplier Scorecard Criteria"
			d["name"] = d.get("criteria_name")
			my_criteria = frappe.get_doc(d)
			my_criteria.insert()
	return my_doc


def delete_test_scorecards():
	my_doc = make_supplier_scorecard()
	if frappe.db.exists("Supplier Scorecard", my_doc.name):
		# Delete all the periods, then delete the scorecard
		frappe.db.sql(
			"""delete from `tabSupplier Scorecard Period` where scorecard = %(scorecard)s""",
			{"scorecard": my_doc.name},
		)
		frappe.db.sql(
			"""delete from `tabSupplier Scorecard Scoring Criteria` where parenttype = 'Supplier Scorecard Period'"""
		)
		frappe.db.sql(
			"""delete from `tabSupplier Scorecard Scoring Standing` where parenttype = 'Supplier Scorecard Period'"""
		)
		frappe.db.sql(
			"""delete from `tabSupplier Scorecard Scoring Variable` where parenttype = 'Supplier Scorecard Period'"""
		)
		frappe.delete_doc(my_doc.doctype, my_doc.name)


valid_scorecard = [
	{
		"standings": [
			{
				"min_grade": 0.0,
				"name": "Very Poor",
				"prevent_rfqs": 1,
				"notify_supplier": 0,
				"doctype": "Supplier Scorecard Scoring Standing",
				"max_grade": 30.0,
				"prevent_pos": 1,
				"warn_pos": 0,
				"warn_rfqs": 0,
				"standing_color": "Red",
				"notify_employee": 0,
				"standing_name": "Very Poor",
				"parenttype": "Supplier Scorecard",
				"parentfield": "standings",
			},
			{
				"min_grade": 30.0,
				"name": "Poor",
				"prevent_rfqs": 1,
				"notify_supplier": 0,
				"doctype": "Supplier Scorecard Scoring Standing",
				"max_grade": 50.0,
				"prevent_pos": 0,
				"warn_pos": 0,
				"warn_rfqs": 0,
				"standing_color": "Red",
				"notify_employee": 0,
				"standing_name": "Poor",
				"parenttype": "Supplier Scorecard",
				"parentfield": "standings",
			},
			{
				"min_grade": 50.0,
				"name": "Average",
				"prevent_rfqs": 0,
				"notify_supplier": 0,
				"doctype": "Supplier Scorecard Scoring Standing",
				"max_grade": 80.0,
				"prevent_pos": 0,
				"warn_pos": 0,
				"warn_rfqs": 0,
				"standing_color": "Green",
				"notify_employee": 0,
				"standing_name": "Average",
				"parenttype": "Supplier Scorecard",
				"parentfield": "standings",
			},
			{
				"min_grade": 80.0,
				"name": "Excellent",
				"prevent_rfqs": 0,
				"notify_supplier": 0,
				"doctype": "Supplier Scorecard Scoring Standing",
				"max_grade": 100.0,
				"prevent_pos": 0,
				"warn_pos": 0,
				"warn_rfqs": 0,
				"standing_color": "Blue",
				"notify_employee": 0,
				"standing_name": "Excellent",
				"parenttype": "Supplier Scorecard",
				"parentfield": "standings",
			},
		],
		"prevent_pos": 0,
		"period": "Per Month",
		"doctype": "Supplier Scorecard",
		"warn_pos": 0,
		"warn_rfqs": 0,
		"notify_supplier": 0,
		"criteria": [
			{
				"weight": 100.0,
				"doctype": "Supplier Scorecard Scoring Criteria",
				"criteria_name": "Delivery",
				"formula": "100",
			}
		],
		"supplier": "_Test Supplier",
		"name": "_Test Supplier",
		"weighting_function": "{total_score} * max( 0, min ( 1 , (12 - {period_number}) / 12) )",
	}
]
