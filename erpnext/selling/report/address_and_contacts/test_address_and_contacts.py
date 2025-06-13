import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.selling.doctype.customer.test_customer import get_customer_dict
from .address_and_contacts import execute


class TestAddressAndContacts(FrappeTestCase):
	def setUp(self):
		self.customer = setup_customer_with_address("Test Customer For Address And Contact")
		self.filters = {"party_type": "Customer", "party_name": self.customer.name}

	def tearDown(self):
		frappe.db.rollback()

	def test_address_and_contacts_report_TC_S_200(self):
		data = execute(self.filters)
		if data[1]:
			for row in data[1]:
				if row[0] == self.customer.name:
					self.assertEqual(row[0], "Test Customer For Address And Contact")
					self.assertEqual(row[1], "All Customer Groups")
					self.assertEqual(row[2], "Hyderabad")
					self.assertEqual(row[3], "Secundrabad")
					self.assertEqual(row[4], "Hyderabad")
					self.assertEqual(row[5], "Telangana")
					self.assertEqual(row[6], "500075")
					self.assertEqual(row[7], "India")
					self.assertEqual(row[8], 1)
					self.assertEqual(row[9], "Test Customer For Address And Contact")
					self.assertEqual(row[10], "Test Last Name")

	def test_customer_without_address_TC_S_201(self):
		customer = frappe.get_doc(get_customer_dict("_Test_Customer_Without_Address_")).insert(
			ignore_permissions=True
		)
		self.filters.update({"party_name": customer.name})
		data = execute(self.filters)
		if data[1]:
			for row in data[1]:
				if row[0] == customer.name:
					self.assertEqual(row[0], "_Test_Customer_Without_Address_")


def setup_customer_with_address(customer_name):
	if not frappe.db.exists("Customer", customer_name):
		frappe.get_doc(
			{
				"doctype": "Customer",
				"customer_name": customer_name,
				"customer_type": "Individual",
				"territory": "All Territories",
				"customer_group": "All Customer Groups",
			}
		).insert(ignore_permissions=True)

		frappe.get_doc(
			{
				"doctype": "Address",
				"address_title": customer_name,
				"address_type": "Billing",
				"address_line1": "Hyderabad",
				"address_line2": "Secundrabad",
				"city": "Hyderabad",
				"state": "Telangana",
				"country": "India",
				"pincode": "500075",
				"is_primary_address": 1,
				"links": [{"link_doctype": "Customer", "link_name": customer_name}],
			}
		).insert(ignore_permissions=True)

		frappe.get_doc(
			{
				"doctype": "Contact",
				"first_name": customer_name,
				"middle_name": "Test Middle Name",
				"last_name": "Test Last Name",
				"status": "Passive",
				"address": customer_name + "-Billing",
				"is_primary_contact": 1,
				"email_ids": [{"email_id": "abcdtest@gmail.com", "is_primary": 1}],
				"phone_nos": [{"phone": "7897895874", "is_primary_phone": 1, "is_primary_mobile_no": 1}],
				"links": [{"link_doctype": "Customer", "link_name": customer_name}],
			}
		).insert(ignore_permissions=True)

	return frappe.get_doc("Customer", customer_name)
