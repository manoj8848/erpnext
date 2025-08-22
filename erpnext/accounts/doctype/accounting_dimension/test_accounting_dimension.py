# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import unittest

import frappe

from erpnext.accounts.doctype.journal_entry.test_journal_entry import make_journal_entry
from erpnext.accounts.doctype.sales_invoice.test_sales_invoice import create_sales_invoice

test_dependencies = ["Cost Center", "Warehouse", "Department"]
if "Assets" in frappe.get_installed_apps():
	test_dependencies = ["Cost Center", "Location", "Warehouse", "Department"]


class TestAccountingDimension(unittest.TestCase):
	def setUp(self):
		create_dimension()

	def test_dimension_against_sales_invoice(self):
		si = create_sales_invoice(do_not_save=1)

		si.location = "Block 1"
		si.append(
			"items",
			{
				"item_code": "_Test Item",
				"warehouse": "_Test Warehouse - _TC",
				"qty": 1,
				"rate": 100,
				"income_account": "Sales - _TC",
				"expense_account": "Cost of Goods Sold - _TC",
				"cost_center": "_Test Cost Center - _TC",
				"department": "_Test Department - _TC",
				"location": "Block 1",
			},
		)

		si.save()
		si.submit()

		gle = frappe.get_doc("GL Entry", {"voucher_no": si.name, "account": "Sales - _TC"})

		self.assertEqual(gle.get("department"), "_Test Department - _TC")

	def test_auto_creation_of_accounts_on_company_creation_TC_ACC_066(self):
		if not frappe.db.exists("Company", "_Test Company"):
			company = frappe.new_doc("Company")
			company.company_name = "_Test Company"
			company.abbr = "_TC"
			company.default_currency = "INR"
			company.create_chart_of_accounts_based_on = "Standard"
			company.save()

		if not frappe.db.exists("Company", "_Test Agro"):
			company = frappe.new_doc("Company")
			company.company_name = "_Test Agro"
			company.abbr = "_TA"
			company.default_currency = "INR"
			company.create_chart_of_accounts_based_on = "Existing Company"
			company.existing_company = "_Test Company"
			company.save()

			expected_results = {
				"Debtors - _TA": {
					"account_type": "Receivable",
					"is_group": 0,
					"root_type": "Asset",
					"parent_account": "Accounts Receivable - _TA",
				},
				"Cash - _TA": {
					"account_type": "Cash",
					"is_group": 0,
					"root_type": "Asset",
					"parent_account": "Cash In Hand - _TA",
				},
			}
			for account, acc_property in expected_results.items():
				acc = frappe.get_doc("Account", account)
				for prop, val in acc_property.items():
					self.assertEqual(acc.get(prop), val)

			frappe.delete_doc("Company", "_Test Agro")

	def test_cost_center_in_gl_and_reports_TC_ACC_067(self):
		# Step 1: Create a Sales Invoice (SI) with a Cost Center
		si = create_sales_invoice(do_not_save=1)
		si.cost_center = "_Test Cost Center - _TC"
		si.location = "Block 1"
		si.append(
			"items",
			{
				"item_code": "_Test Item",
				"warehouse": "_Test Warehouse - _TC",
				"qty": 1,
				"rate": 100,
				"income_account": "Sales - _TC",
				"expense_account": "Cost of Goods Sold - _TC",
				"cost_center": "_Test Cost Center - _TC",
				"department": "_Test Department - _TC",
				"location": "Block 1",
			},
		)

		si.save()
		si.submit()

		# Step 2: Verify Cost Center appears in the General Ledger
		gl_entries = frappe.db.get_all(
			"GL Entry",
			filters={"voucher_no": si.name},
			fields=["account", "cost_center", "debit", "credit"],
		)

		# Assert that GL Entries include the specified Cost Center
		self.assertTrue(
			any(entry["cost_center"] == "_Test Cost Center - _TC" for entry in gl_entries),
			"Cost Center not reflected in GL Entries",
		)

		# Step 3: Verify Cost Center in Profit and Loss Report
		profit_and_loss_data = frappe.get_list(
			"GL Entry",
			filters={"account": "Sales - _TC", "cost_center": "_Test Cost Center - _TC"},
			fields=["account", "debit", "credit", "cost_center"],
		)
		self.assertGreater(len(profit_and_loss_data), 0, "Cost Center not reflected in P&L Report")

		# Step 4: Verify Cost Center in Balance Sheet Report
		balance_sheet_data = frappe.get_list(
			"GL Entry",
			filters={"cost_center": "_Test Cost Center - _TC"},
			fields=["account", "debit", "credit", "cost_center"],
		)
		self.assertGreater(len(balance_sheet_data), 0, "Cost Center not reflected in Balance Sheet")

	def test_dimension_against_journal_entry(self):
		je = make_journal_entry("Sales - _TC", "Sales Expenses - _TC", 500, save=False)
		je.accounts[0].update({"department": "_Test Department - _TC"})
		je.accounts[1].update({"department": "_Test Department - _TC"})

		je.accounts[0].update({"location": "Block 1"})
		je.accounts[1].update({"location": "Block 1"})

		je.save()
		je.submit()

		gle = frappe.get_doc("GL Entry", {"voucher_no": je.name, "account": "Sales - _TC"})
		gle1 = frappe.get_doc("GL Entry", {"voucher_no": je.name, "account": "Sales Expenses - _TC"})
		self.assertEqual(gle.get("department"), "_Test Department - _TC")
		self.assertEqual(gle1.get("department"), "_Test Department - _TC")

	def test_mandatory(self):
		si = create_sales_invoice(do_not_save=1)
		si.append(
			"items",
			{
				"item_code": "_Test Item",
				"warehouse": "_Test Warehouse - _TC",
				"qty": 1,
				"rate": 100,
				"income_account": "Sales - _TC",
				"expense_account": "Cost of Goods Sold - _TC",
				"cost_center": "_Test Cost Center - _TC",
				"location": "",
			},
		)

		si.save()
		self.assertRaises(frappe.ValidationError, si.submit)

	def tearDown(self):
		disable_dimension()
		frappe.flags.accounting_dimensions_details = None
		frappe.flags.dimension_filter_map = None

	def test_validate_core_doctypes_not_allowed_TC_ACC_200(self):
		self.doc = frappe.get_doc({"doctype": "Accounting Dimension", "document_type": "Test DocType"})
		"""Test that core doctypes cannot be used as accounting dimensions"""
		core_doctypes = [
			"User",
			"Role",
			"Module Def",
			"DocType",
			"Accounting Dimension",
			"Project",
			"Cost Center",
		]

		for doctype in core_doctypes:
			self.doc.document_type = doctype
			with self.assertRaises(frappe.ValidationError) as cm:
				self.doc.validate_doctype()
			self.assertIn(f"Not allowed to create accounting dimension for {doctype}", str(cm.exception))

	def test_on_trash_deletes_dimension_fields_and_property_setters_TC_ACC_201(self):
		from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import (
			get_doctypes_with_dimensions,
		)

		frappe.flags.in_test = True  # Force synchronous delete

		if not frappe.db.exists("Property Setter", "Budget-budget_against-options"):
			frappe.get_doc(
				{
					"doctype": "Property Setter",
					"name": "Budget-budget_against-options",
					"property": "options",
					"property_type": "Text",
					"value": "\nCost Center\nProject\nMyTestDocType",
					"doc_type": "Budget",
					"field_name": "budget_against",
				}
			).insert()

		self.test_doc, doclist = prepare_test_dimension_and_fields(include_property_setter=True)

		# Trigger validate and on_trash
		self.test_doc.validate()
		self.test_doc.on_trash()

		# Verify Custom Fields are deleted
		for dt in doclist:
			self.assertFalse(frappe.db.exists("Custom Field", {"dt": dt, "fieldname": "test_dimension"}))
			self.assertFalse(
				frappe.db.exists("Custom Field", {"dt": dt, "fieldname": "source_test_dimension"})
			)
			self.assertFalse(
				frappe.db.exists("Custom Field", {"dt": dt, "fieldname": "target_test_dimension"})
			)

			# Verify Property Setter deleted
			self.assertFalse(
				frappe.db.exists("Property Setter", {"doc_type": dt, "field_name": "test_dimension"})
			)

		# Clean up
		frappe.db.sql("DELETE FROM `tabAccounting Dimension` WHERE fieldname = 'test_dimension'")
		frappe.db.sql(
			"DELETE FROM `tabCustom Field` WHERE fieldname IN ('test_dimension', 'source_test_dimension', 'target_test_dimension')"
		)
		frappe.db.sql("DELETE FROM `tabProperty Setter` WHERE field_name = 'test_dimension'")

		# Restore Budget-budget_against-options
		ps = frappe.get_doc("Property Setter", "Budget-budget_against-options")
		ps.value = "\nCost Center\nProject\nMyTestDocType"
		ps.save()

		frappe.flags.in_test = False

	def test_disable_dimension_TC_ACC_202(self):
		import json

		from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import disable_dimension

		frappe.flags.in_test = True  # Force synchronous

		# Use refactored helper
		self.test_doc, doclist = prepare_test_dimension_and_fields()

		# Disable dimension
		disable_dimension(json.dumps({"fieldname": "test_dimension", "disabled": 1}))

		# Verify read_only = 1
		for dt in doclist:
			val = frappe.db.get_value("Custom Field", {"dt": dt, "fieldname": "test_dimension"}, "read_only")
			self.assertEqual(val, 1)

			if dt == "Asset Movement Item":
				val_source = frappe.db.get_value(
					"Custom Field", {"dt": dt, "fieldname": "source_test_dimension"}, "read_only"
				)
				val_target = frappe.db.get_value(
					"Custom Field", {"dt": dt, "fieldname": "target_test_dimension"}, "read_only"
				)
				self.assertEqual(val_source, 1)
				self.assertEqual(val_target, 1)

		# Enable dimension again
		disable_dimension(json.dumps({"fieldname": "test_dimension", "disabled": 0}))

		# Verify read_only = 0
		for dt in doclist:
			val = frappe.db.get_value("Custom Field", {"dt": dt, "fieldname": "test_dimension"}, "read_only")
			self.assertEqual(val, 0)

			if dt == "Asset Movement Item":
				val_source = frappe.db.get_value(
					"Custom Field", {"dt": dt, "fieldname": "source_test_dimension"}, "read_only"
				)
				val_target = frappe.db.get_value(
					"Custom Field", {"dt": dt, "fieldname": "target_test_dimension"}, "read_only"
				)
				self.assertEqual(val_source, 0)
				self.assertEqual(val_target, 0)

	def test_get_dimension_with_children_TC_ACC_203(self):
		from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import (
			get_dimension_with_children,
		)

		frappe.flags.in_test = True
		root_cost_center = frappe.get_value("Company", "_Test Company", "name")

		# Create parent Cost Center
		if not frappe.db.exists("Cost Center", "_Test Cost Center1 - _TC"):
			frappe.get_doc(
				{
					"doctype": "Cost Center",
					"cost_center_name": "_Test Cost Center1",
					"company": "_Test Company",
					"parent_cost_center": f"{root_cost_center} - _TC",
					"is_group": 1,
				}
			).insert()

		# Create child 1
		if not frappe.db.exists("Cost Center", "_Test Child 1 - _TC"):
			frappe.get_doc(
				{
					"doctype": "Cost Center",
					"cost_center_name": "_Test Child 1",
					"company": "_Test Company",
					"parent_cost_center": "_Test Cost Center1 - _TC",
					"is_group": 0,
				}
			).insert()

		# Create child 2
		if not frappe.db.exists("Cost Center", "_Test Child 2 - _TC"):
			frappe.get_doc(
				{
					"doctype": "Cost Center",
					"cost_center_name": "_Test Child 2",
					"company": "_Test Company",
					"parent_cost_center": "_Test Cost Center1 - _TC",
					"is_group": 0,
				}
			).insert()

		# Now test on the correct parent!
		children = get_dimension_with_children("Cost Center", "_Test Cost Center1 - _TC")

		# Correct assertions
		self.assertIn("_Test Cost Center1 - _TC", children)
		self.assertIn("_Test Child 1 - _TC", children)
		self.assertIn("_Test Child 2 - _TC", children)

		frappe.flags.in_test = False

	def test_create_accounting_dimensions_for_doctype_TC_ACC_204(self):
		from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import (
			create_accounting_dimensions_for_doctype,
		)

		frappe.flags.in_test = True

		# Prepare test Accounting Dimension
		self.test_doc, _ = prepare_test_dimension_and_fields()

		# Delete any existing Custom Field for this dimension in MyTestDocType
		frappe.db.sql(
			"DELETE FROM `tabCustom Field` WHERE dt = %s AND fieldname = %s",
			("MyTestDocType", "test_dimension"),
		)

		# Run create_accounting_dimensions_for_doctype
		create_accounting_dimensions_for_doctype("MyTestDocType")

		# Verify Custom Field was created
		field_exists = frappe.db.exists(
			"Custom Field", {"dt": "MyTestDocType", "fieldname": "test_dimension"}
		)
		self.assertTrue(field_exists)

		# Verify properties
		field = frappe.get_doc("Custom Field", {"dt": "MyTestDocType", "fieldname": "test_dimension"})
		self.assertEqual(field.fieldtype, "Link")
		self.assertEqual(field.options, "MyTestDocType")
		self.assertEqual(field.insert_after, "accounting_dimensions_section")

		# Clean up
		frappe.db.sql("DELETE FROM `tabAccounting Dimension` WHERE fieldname = 'test_dimension'")
		frappe.db.sql("DELETE FROM `tabCustom Field` WHERE fieldname = 'test_dimension'")
		frappe.flags.in_test = False


def prepare_test_dimension_and_fields(include_property_setter=False):
	from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import (
		get_doctypes_with_dimensions,
	)

	doclist = get_doctypes_with_dimensions()

	# MyTestDocType exists or create
	if not frappe.db.exists("DocType", "MyTestDocType"):
		frappe.get_doc(
			{
				"doctype": "DocType",
				"name": "MyTestDocType",
				"module": "Custom",
				"custom": 1,
				"fields": [],
				"permissions": [{"role": "System Manager", "read": 1, "write": 1}],
			}
		).insert()

	# Create test Accounting Dimension
	existing_dimension = frappe.db.exists("Accounting Dimension", {"document_type": "MyTestDocType"})
	if existing_dimension:
		test_doc = frappe.get_doc("Accounting Dimension", existing_dimension)
	else:
		test_doc = frappe.get_doc(
			{
				"doctype": "Accounting Dimension",
				"label": "Test Dimension",
				"fieldname": "test_dimension",
				"document_type": "MyTestDocType",
			}
		)
		test_doc.insert()
		test_doc.reload()

	# Create Custom Fields (and optional Property Setter)
	for dt in doclist:
		# Main field
		if not frappe.db.exists("Custom Field", {"dt": dt, "fieldname": "test_dimension"}):
			frappe.get_doc({"doctype": "Custom Field", "dt": dt, "fieldname": "test_dimension"}).insert()

		# source_/target_ fields only for Asset Movement Item
		if dt == "Asset Movement Item":
			if not frappe.db.exists("Custom Field", {"dt": dt, "fieldname": "source_test_dimension"}):
				frappe.get_doc(
					{"doctype": "Custom Field", "dt": dt, "fieldname": "source_test_dimension"}
				).insert()

			if not frappe.db.exists("Custom Field", {"dt": dt, "fieldname": "target_test_dimension"}):
				frappe.get_doc(
					{"doctype": "Custom Field", "dt": dt, "fieldname": "target_test_dimension"}
				).insert()

		# Property Setter (if requested)
		if include_property_setter:
			if not frappe.db.exists("Property Setter", {"doc_type": dt, "field_name": "test_dimension"}):
				frappe.get_doc(
					{
						"doctype": "Property Setter",
						"doc_type": dt,
						"field_name": "test_dimension",
						"property": "label",
						"value": "Test Dimension Label",
						"doctype_or_field": "DocField",
					}
				).insert()

	return test_doc, doclist


def create_dimension():
	frappe.set_user("Administrator")

	if not frappe.db.exists("Accounting Dimension", {"document_type": "Department"}):
		dimension = frappe.get_doc(
			{
				"doctype": "Accounting Dimension",
				"document_type": "Department",
			}
		)
		dimension.append(
			"dimension_defaults",
			{
				"company": "_Test Company",
				"reference_document": "Department",
				"default_dimension": "_Test Department - _TC",
			},
		)
		dimension.insert()
		dimension.save()
	else:
		dimension = frappe.get_doc("Accounting Dimension", "Department")
		dimension.disabled = 0
		dimension.save()

	if "Assets" in frappe.get_installed_apps():
		if not frappe.db.exists("Accounting Dimension", {"document_type": "Location"}):
			dimension1 = frappe.get_doc(
				{
					"doctype": "Accounting Dimension",
					"document_type": "Location",
				}
			)

			dimension1.append(
				"dimension_defaults",
				{
					"company": "_Test Company",
					"reference_document": "Location",
					"default_dimension": "Block 1",
					"mandatory_for_bs": 1,
				},
			)

			dimension1.insert()
			dimension1.save()
		else:
			dimension1 = frappe.get_doc("Accounting Dimension", "Location")
			dimension1.disabled = 0
			dimension1.save()


def disable_dimension():
	dimension1 = frappe.get_doc("Accounting Dimension", "Department")
	dimension1.disabled = 1
	dimension1.save()
	if "Assets" in frappe.get_installed_apps():
		dimension2 = frappe.get_doc("Accounting Dimension", "Location")
		dimension2.disabled = 1
		dimension2.save()
