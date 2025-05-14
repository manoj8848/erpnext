# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt


import frappe
from frappe.test_runner import make_test_records

from erpnext.accounts.party import get_due_date
from erpnext.controllers.website_list_for_contact import get_customers_suppliers
from erpnext.exceptions import PartyDisabled

test_dependencies = ["Payment Term", "Payment Terms Template"]
test_records = frappe.get_test_records("Supplier")

from frappe.tests.utils import FrappeTestCase


class TestSupplier(FrappeTestCase):
	def test_get_supplier_group_details(self):
		doc = frappe.new_doc("Supplier Group")
		doc.supplier_group_name = "_Testing Supplier Group"
		doc.payment_terms = "_Test Payment Term Template 3"
		doc.accounts = []
		test_account_details = {
			"company": "_Test Company",
			"account": "Creditors - _TC",
		}
		doc.append("accounts", test_account_details)
		doc.save()
		s_doc = frappe.new_doc("Supplier")
		s_doc.supplier_name = "Testing Supplier"
		s_doc.supplier_group = "_Testing Supplier Group"
		s_doc.payment_terms = ""
		s_doc.accounts = []
		s_doc.insert()
		s_doc.get_supplier_group_details()
		self.assertEqual(s_doc.payment_terms, "_Test Payment Term Template 3")
		self.assertEqual(s_doc.accounts[0].company, "_Test Company")
		self.assertEqual(s_doc.accounts[0].account, "Creditors - _TC")
		s_doc.delete()
		doc.delete()

	def test_supplier_default_payment_terms(self):
		# Payment Term based on Days after invoice date
		frappe.db.set_value(
			"Supplier", "_Test Supplier With Template 1", "payment_terms", "_Test Payment Term Template 3"
		)

		due_date = get_due_date("2016-01-22", "Supplier", "_Test Supplier With Template 1")
		self.assertEqual(due_date, "2016-02-21")

		due_date = get_due_date("2017-01-22", "Supplier", "_Test Supplier With Template 1")
		self.assertEqual(due_date, "2017-02-21")

		# Payment Term based on last day of month
		frappe.db.set_value(
			"Supplier", "_Test Supplier With Template 1", "payment_terms", "_Test Payment Term Template 1"
		)

		due_date = get_due_date("2016-01-22", "Supplier", "_Test Supplier With Template 1")
		self.assertEqual(due_date, "2016-02-29")

		due_date = get_due_date("2017-01-22", "Supplier", "_Test Supplier With Template 1")
		self.assertEqual(due_date, "2017-02-28")

		frappe.db.set_value("Supplier", "_Test Supplier With Template 1", "payment_terms", "")

		# Set credit limit for the supplier group instead of supplier and evaluate the due date
		frappe.db.set_value(
			"Supplier Group", "_Test Supplier Group", "payment_terms", "_Test Payment Term Template 3"
		)

		due_date = get_due_date("2016-01-22", "Supplier", "_Test Supplier With Template 1")
		self.assertEqual(due_date, "2016-02-21")

		# Payment terms for Supplier Group instead of supplier and evaluate the due date
		frappe.db.set_value(
			"Supplier Group", "_Test Supplier Group", "payment_terms", "_Test Payment Term Template 1"
		)

		# Leap year
		due_date = get_due_date("2016-01-22", "Supplier", "_Test Supplier With Template 1")
		self.assertEqual(due_date, "2016-02-29")
		# # Non Leap year
		due_date = get_due_date("2017-01-22", "Supplier", "_Test Supplier With Template 1")
		self.assertEqual(due_date, "2017-02-28")

		# Supplier with no default Payment Terms Template
		frappe.db.set_value("Supplier Group", "_Test Supplier Group", "payment_terms", "")
		frappe.db.set_value("Supplier", "_Test Supplier", "payment_terms", "")

		due_date = get_due_date("2016-01-22", "Supplier", "_Test Supplier")
		self.assertEqual(due_date, "2016-01-22")
		# # Non Leap year
		due_date = get_due_date("2017-01-22", "Supplier", "_Test Supplier")
		self.assertEqual(due_date, "2017-01-22")

	def test_supplier_disabled(self):
		make_test_records("Item")

		frappe.db.set_value("Supplier", "_Test Supplier", "disabled", 1)

		from erpnext.buying.doctype.purchase_order.test_purchase_order import create_purchase_order

		po = create_purchase_order(do_not_save=True)

		self.assertRaises(PartyDisabled, po.save)

		frappe.db.set_value("Supplier", "_Test Supplier", "disabled", 0)

		po.save()

	def test_supplier_country(self):
		# Test that country field exists in Supplier DocType
		supplier = frappe.get_doc("Supplier", "_Test Supplier with Country")
		self.assertTrue("country" in supplier.as_dict())

		# Test if test supplier field record is 'Greece'
		self.assertEqual(supplier.country, "Greece")

		# Test update Supplier instance country value
		supplier = frappe.get_doc("Supplier", "_Test Supplier")
		supplier.country = "Greece"
		supplier.save()
		self.assertEqual(supplier.country, "Greece")

	def test_party_details_tax_category(self):
		from erpnext.accounts.party import get_party_details

		frappe.delete_doc_if_exists("Address", "_Test Address With Tax Category-Billing")

		# Tax Category without Address
		details = get_party_details("_Test Supplier With Tax Category", party_type="Supplier")
		self.assertEqual(details.tax_category, "_Test Tax Category 1")

		address = frappe.get_doc(
			dict(
				doctype="Address",
				address_title="_Test Address With Tax Category",
				tax_category="_Test Tax Category 2",
				address_type="Billing",
				address_line1="Station Road",
				city="_Test City",
				country="India",
				links=[dict(link_doctype="Supplier", link_name="_Test Supplier With Tax Category")],
			)
		).insert()

		# Tax Category with Address
		details = get_party_details("_Test Supplier With Tax Category", party_type="Supplier")
		self.assertEqual(details.tax_category, "_Test Tax Category 2")

		# Rollback
		address.delete()

	def setUp(self):
		self.supplier = create_supplier(supplier_name = "Test Supplier for Contact")

		self.contact = frappe.get_doc({
            "doctype": "Contact",
            "first_name": "John",
            "last_name": "Doe",
            "email_id": "john.doe@example.com",
            "links": [{
                "link_doctype": "Supplier",
                "link_name": self.supplier.name
            }]
        }).insert(ignore_permissions=True)

	def test_get_supplier_primary_contact_TC_B_181(self):
		from erpnext.buying.doctype.supplier.supplier import get_supplier_primary_contact
		results = get_supplier_primary_contact(
		doctype="Contact",
		txt="John",
		searchfield="name",
		start=0,
		page_len=10,
		filters={"supplier": self.supplier.name}
		)

		self.assertTrue(results)
		self.assertIn(self.contact.name, results[0])

	def test_create_primary_contact_TC_B_182(self):
		supplier = frappe.get_doc({
            "doctype": "Supplier",
            "supplier_name": "Test Supplier",
            "supplier_group": "All Supplier Groups",
            "mobile_no": "1234567890",
            "email_id": "test@example.com"
        })
		supplier.insert(ignore_permissions=True)

		supplier.create_primary_contact()

		supplier.reload()

		self.assertIsNotNone(supplier.supplier_primary_contact)
		self.assertEqual(supplier.mobile_no, "1234567890")
		self.assertEqual(supplier.email_id, "test@example.com")

	def test_create_primary_address_TC_B_183(self):
			supplier = frappe.get_doc({
				"doctype": "Supplier",
				"supplier_name": "Test Supplier",
				"supplier_group": "All Supplier Groups",
				"address_line1": "Testt",
				"city": "Pune",
				"state": "Maharashtra",
				"country": "India",
				"pincode": "411018"
			})
			supplier.insert(ignore_if_duplicate=True, ignore_permissions=True)

			supplier.create_primary_address()

			supplier.reload()

			self.assertIsNotNone(supplier.supplier_primary_address)
			self.assertIsNotNone(supplier.primary_address)
			self.assertIn("Testt", supplier.primary_address)

	def test_after_rename_TC_B_184(self):
		supplier = frappe.get_doc({
			"doctype": "Supplier",
			"supplier_name": "Original Name",
			"supplier_group": "All Supplier Groups"
		})
		supplier.insert(ignore_permissions=True)

		frappe.db.set_default("supp_master_name", "Supplier Name")

		new_name = "Renamed Supplier"
		frappe.rename_doc("Supplier", supplier.name, new_name, force=True)
		renamed = frappe.get_doc("Supplier", new_name)

		self.assertEqual(renamed.name, new_name)
		self.assertEqual(renamed.supplier_name, new_name)

	def test_on_trash_TC_B_185(self):
		supplier = frappe.get_doc({
			"doctype": "Supplier",
			"supplier_name": "Test Trash Supplier",
			"supplier_group": "All Supplier Groups",
			"address_line1": "Testt",
			"city": "Pune",
			"state": "Maharashtra",
			"country": "India",
			"pincode": "411018",
			"mobile_no": "1234567890",
            "email_id": "test@example.com"
		})
		supplier.insert(ignore_permissions=True)

		supplier.delete()

		self.assertFalse(frappe.db.exists("Supplier", supplier.name))

	def test__add_supplier_role_TC_B_186(self):
		from frappe.utils import random_string

		user_email = f"test_supplier_{random_string(5)}@example.com"
		user = frappe.new_doc("User")
		user.email = user_email
		user.first_name = "Test"
		user.send_welcome_email = 0
		user.save(ignore_permissions=True)

		user.set("roles", [])
		user.save(ignore_permissions=True)

		class DummyPortalUser:
			def __init__(self, user):
				self.user = user
			def is_new(self):
				return True

		portal_user = DummyPortalUser(user.name)

		supplier = frappe.new_doc("Supplier")
		supplier._add_supplier_role(portal_user)

		user.reload()
		roles = [r.role for r in user.roles]
		self.assertIn("Supplier", roles)

def create_supplier(**args):
	args = frappe._dict(args)

	if not args.supplier_name:
		args.supplier_name = frappe.generate_hash()

	if frappe.db.exists("Supplier", args.supplier_name):
		return frappe.get_doc("Supplier", args.supplier_name)

	doc = frappe.get_doc(
		{
			"doctype": "Supplier",
			"supplier_name": args.supplier_name,
			"default_currency": args.default_currency,
			"supplier_type": args.supplier_type or "Company",
			"tax_withholding_category": args.tax_withholding_category,
		}
	)
	if not args.without_supplier_group:
		doc.supplier_group = args.supplier_group or "Services"

	doc.insert(ignore_permissions=True)

	return doc


class TestSupplierPortal(FrappeTestCase):
	def test_portal_user_can_access_supplier_data(self):
		supplier = create_supplier()

		user = frappe.generate_hash() + "@example.com"
		frappe.new_doc(
			"User",
			first_name="Supplier Portal User",
			email=user,
			send_welcome_email=False,
		).insert()

		supplier.append("portal_users", {"user": user})
		supplier.save()
		current_user = frappe.session.user
		frappe.set_user(user)
		_, suppliers = get_customers_suppliers("Purchase Order", user)

		self.assertIn(supplier.name, suppliers)
		frappe.db.rollback()
		frappe.set_user(current_user)
		frappe.delete_doc("User", user)
