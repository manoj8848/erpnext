import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.accounts.doctype.sales_invoice.test_sales_invoice import get_active_fiscal_year

from .territory_target_variance_based_on_item_group import execute


class TestTerritoryTargetVarianceBasedOnItemGroup(FrappeTestCase):
	def setUp(self):
		prepared_data = setup_data()
		self.territory = prepared_data.get("territory")

	def tearDown(self):
		frappe.db.rollback()

	def test_territory_target_variance_report_TC_S_220(self):
		filters = frappe._dict(
			fiscal_year=get_active_fiscal_year(),
			doctype="Sales Order",
			period="Monthly",
			target_on="Quantity",
		)

		data = execute(filters)
		if data[1]:
			for row in data[1]:
				if row.get("territory") == self.territory:
					self.assertEqual(row.get("territory"), "_Test Territory Target Variance")
					self.assertEqual(row.get("item_group"), "_Test Item Group")


def setup_data():
	territory = "_Test Territory Target Variance"
	distribution = "_Test Territory Target Variance Distribution"
	month_list = [
		"January",
		"February",
		"March",
		"April",
		"May",
		"June",
		"July",
		"August",
		"September",
		"October",
		"November",
		"December",
	]
	if not frappe.db.exists("Monthly Distribution", distribution):
		doc = frappe.get_doc({"doctype": "Monthly Distribution", "distribution_id": distribution})
		for idx, month in enumerate(month_list, start=1):
			doc.append("percentages", {"month": month, "percentage_allocation": 8.333, "idx": idx})
		doc.save(ignore_permissions=True)

	if not frappe.db.exists("Territory", territory):
		frappe.get_doc(
			{
				"doctype": "Territory",
				"territory_name": territory,
				"parent_territory": "All Territories",
				"targets": [
					{
						"item_group": "_Test Item Group",
						"fiscal_year": get_active_fiscal_year(),
						"target_qty": 10,
						"target_amount": 100,
						"distribution_id": distribution,
					}
				],
			}
		).insert(ignore_permissions=True)

	return {"territory": territory, "distribution": distribution}
