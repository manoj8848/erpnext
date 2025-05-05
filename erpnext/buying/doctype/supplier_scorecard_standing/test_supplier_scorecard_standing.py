# Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import frappe
import unittest

from .supplier_scorecard_standing import get_scoring_standing, get_standings_list

class TestSupplierScorecardStanding(unittest.TestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_scorecard_standing_TC_B_180(self):
		scorecard_standing = frappe.get_doc(
			{
				"doctype": "Supplier Scorecard Standing",
				"standing_name": "test_standing" + frappe.generate_hash(length=5),
				"standing_color": "Blue",
				"mingrade": 0,
				"max_grade": 100
			}
		)
		scorecard_standing.insert(ignore_permissions=True)

		scorecard_standing.load_from_db()
		self.assertTrue(get_scoring_standing(scorecard_standing.name))
		self.assertTrue(get_standings_list())