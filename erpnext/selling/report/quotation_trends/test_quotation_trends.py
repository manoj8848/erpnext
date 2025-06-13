import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.accounts.doctype.payment_entry.test_payment_entry import make_test_item
from erpnext.accounts.doctype.sales_invoice.test_sales_invoice import get_active_fiscal_year
from erpnext.selling.doctype.customer.test_customer import get_customer_dict_new
from erpnext.selling.doctype.quotation.test_quotation import make_quotation
from erpnext.selling.report.quotation_trends.quotation_trends import execute


class TestQuotationTrends(FrappeTestCase):
	def setUp(self):
		self.item = make_test_item("Test Quotation Trends Item")
		self.customer = frappe.get_doc(get_customer_dict_new("Test Quotation Trends Customer")).insert(
			ignore_permissions=True
		)

		qo = make_quotation(item_code=self.item.item_code, party_name=self.customer.name, do_not_save=True)
		qo.insert(ignore_permissions=True)
		qo.submit()
		self.filters = frappe._dict(
			company="_Test Company", period="Monthly", fiscal_year=get_active_fiscal_year(), based_on="Item"
		)

	def tearDown(self):
		frappe.db.rollback()

	def test_quotation_trends_report_TC_S_213(self):
		# based on item
		data = execute(self.filters)
		for row in data[1]:
			if row[0] == self.item.item_code:
				self.assertEqual(row[0], "Test Quotation Trends Item")

		# based on item group
		self.filters.update({"based_on": "Customer"})
		customer_data = execute(self.filters)
		for row_1 in customer_data[1]:
			if row_1[0] == self.customer.name:
				self.assertEqual(row_1[0], "Test Quotation Trends Customer")

		# based on group by
		self.filters.update({"group_by": "Item"})
		group_data = execute(self.filters)
		for row_3 in group_data[1]:
			if row_3[0] == self.customer.name:
				self.assertEqual(row_3[0], "Test Quotation Trends Customer")
