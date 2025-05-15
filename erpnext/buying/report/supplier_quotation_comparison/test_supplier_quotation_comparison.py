import frappe

from frappe.utils import today, add_days
from frappe.tests.utils import FrappeTestCase

from erpnext.buying.report.supplier_quotation_comparison.supplier_quotation_comparison import execute

class TestSupplierQuotationComparison(FrappeTestCase):
	def setUp(self):
		sq = create_supplier_quotation()
		sq.transaction_date = today()
		sq.insert()
		sq.submit()

		self.filters = {
			"company": sq.company,
			"from_date": add_days(today(), -1),
			"to_date": today()
		}

	def tearDown(self):
		frappe.db.rollback()

	def test_supplier_quotation_data_codecov(self):
		data = execute(self.filters)
		item_data = data[1][0]
		self.assertEqual(item_data.get("item_code"), "_Test FG Item")
		self.assertEqual(item_data.get("supplier_name"), "_Test Supplier")

		# based on group by Item
		self.filters["group_by"] = "Group by Item"
		group_data = execute(self.filters)
		item_group_data = group_data[1][0]
		self.assertEqual(item_group_data.get("item_code"), "_Test FG Item")
		self.assertEqual(item_group_data.get("supplier_name"), "_Test Supplier")

		# based on group by supplier
		self.filters["group_by"] = "Group by Supplier"
		s_data = execute(self.filters)
		supplier_group_data = s_data[1][0]
		self.assertEqual(supplier_group_data.get("item_code"), "_Test FG Item")
		self.assertEqual(supplier_group_data.get("supplier_name"), "_Test Supplier")

		self.filters["include_expired"] = 1
		e_data = execute(self.filters)
		expired_data = e_data[1][0]
		self.assertEqual(expired_data.get("item_code"), "_Test FG Item")
		self.assertEqual(expired_data.get("supplier_name"), "_Test Supplier")

def create_supplier_quotation():
	sq = frappe.copy_doc(test_records[0]).insert()
	sq = frappe.get_doc("Supplier Quotation", sq.name)

	return sq

test_records = frappe.get_test_records("Supplier Quotation")