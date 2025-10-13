# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt
import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.controllers.queries import item_query

test_dependencies = ["Item", "Customer", "Supplier"]


def create_party_specific_item(**args):
	psi = frappe.new_doc("Party Specific Item")
	psi.party_type = args.get("party_type")
	psi.party = args.get("party")
	psi.restrict_based_on = args.get("restrict_based_on")
	psi.based_on_value = args.get("based_on_value")
	psi.insert()


class TestPartySpecificItem(FrappeTestCase):
	def setUp(self):
		self.create_customer()
		self.create_supplier()
		self.create_item()

	def create_customer(self):
		name = "_Test PSI Customer"
		if frappe.db.exists("Customer", name):
			self.customer = name
		else:
			customer = frappe.new_doc("Customer")
			customer.customer_name = name
			customer.customer_type = "Individual"
			customer.save()
			self.customer = customer.name

	def create_supplier(self):
		name = "_Test Supplier"
		if frappe.db.exists("Supplier", name):
			self.supplier = name
		else:
			supplier = frappe.new_doc("Supplier")
			supplier.supplier_name = "_Test Supplier"
			supplier.supplier_group = "All Supplier Groups"
			supplier.save()
			self.supplier = supplier.name

	def create_item(self):
		name = "_Test PSI Item"
		if frappe.db.exists("Item", name):
			self.item = name
		else:
			item = frappe.new_doc("Item")
			item.item_code = name
			item.item_name = "Test PSI Item"
			item.item_group = "All Item Groups"
			item.is_stock_item = 0
			item.gst_hsn_code = "100111222"
			item.stock_uom = "Nos"
			item.save(ignore_permissions=True)
			self.item = item.name

	def test_item_query_for_customer(self):
		create_party_specific_item(
			party_type="Customer",
			party=self.customer.name,
			restrict_based_on="Item",
			based_on_value=self.item.name,
		)
		filters = {"is_sales_item": 1, "customer": self.customer.name}
		items = item_query(
			doctype="Item", txt="", searchfield="name", start=0, page_len=20, filters=filters, as_dict=False
		)
		for item in items:
			self.assertEqual(item[0], self.item.name)

	def test_item_query_for_supplier(self):
		create_party_specific_item(
			party_type="Supplier",
			party=self.supplier,
			restrict_based_on="Item Group",
			based_on_value=frappe.db.get_value("Item", self.item, "item_group"),
		)
		filters = {"supplier": self.supplier.name, "is_purchase_item": 1}
		items = item_query(
			doctype="Item", txt="", searchfield="name", start=0, page_len=20, filters=filters, as_dict=False
		)
		expected_group = frappe.db.get_value("Item", self.item, "item_group")
		for item in items:
			self.assertEqual(item[2], expected_group)

	def test_duplicate_entry_TC_B_199(self):
		party_specific_item_1 = get_party_specific_item(
			party_type="Customer",
			party=self.customer,
			restrict_based_on="Item",
			based_on_value=self.item,
		)
		party_specific_item_1.insert(ignore_permissions=True)

		party_specific_item_2 = get_party_specific_item(
			party_type="Customer",
			party=self.customer,
			restrict_based_on="Item",
			based_on_value=self.item,
		)
		self.assertRaises(frappe.ValidationError, party_specific_item_2.save)

def get_party_specific_item(**args):
	doc = frappe.new_doc("Party Specific Item")
	doc.party_type = args.get("party_type")
	doc.party = args.get("party")
	doc.restrict_based_on = args.get("restrict_based_on")
	doc.based_on_value = args.get("based_on_value")

	return doc