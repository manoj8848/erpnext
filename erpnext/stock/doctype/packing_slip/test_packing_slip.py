# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt


import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.selling.doctype.product_bundle.test_product_bundle import make_product_bundle
from erpnext.stock.doctype.delivery_note.delivery_note import make_packing_slip
from erpnext.stock.doctype.delivery_note.test_delivery_note import create_delivery_note
from erpnext.stock.doctype.item.test_item import make_item


class TestPackingSlip(FrappeTestCase):
	def test_packing_slip(self):
		# Step - 1: Create a Product Bundle
		items = create_items()
		make_product_bundle(items[0], items[1:], 5)

		# Step - 2: Create a Delivery Note (Draft) with Product Bundle
		dn = create_delivery_note(
			item_code=items[0],
			qty=2,
			do_not_save=True,
		)
		dn.append(
			"items",
			{
				"item_code": items[1],
				"warehouse": "_Test Warehouse - _TC",
				"qty": 10,
			},
		)
		dn.save()

		# Step - 3: Make a Packing Slip from Delivery Note for 4 Qty
		ps1 = make_packing_slip(dn.name)
		for item in ps1.items:
			item.qty = 4
		ps1.save()
		ps1.submit()

		# Test - 1: `Packed Qty` should be updated to 4 in Delivery Note Items and Packed Items.
		dn.load_from_db()
		for item in dn.items:
			if not frappe.db.exists("Product Bundle", {"new_item_code": item.item_code}):
				self.assertEqual(item.packed_qty, 4)

		for item in dn.packed_items:
			self.assertEqual(item.packed_qty, 4)

		# Step - 4: Make another Packing Slip from Delivery Note for 6 Qty
		ps2 = make_packing_slip(dn.name)
		ps2.save()
		ps2.submit()

		# Test - 2: `Packed Qty` should be updated to 10 in Delivery Note Items and Packed Items.
		dn.load_from_db()
		for item in dn.items:
			if not frappe.db.exists("Product Bundle", {"new_item_code": item.item_code}):
				self.assertEqual(item.packed_qty, 10)

		for item in dn.packed_items:
			self.assertEqual(item.packed_qty, 10)

		# Step - 5: Cancel Packing Slip [1]
		ps1.cancel()

		# Test - 3: `Packed Qty` should be updated to 4 in Delivery Note Items and Packed Items.
		dn.load_from_db()
		for item in dn.items:
			if not frappe.db.exists("Product Bundle", {"new_item_code": item.item_code}):
				self.assertEqual(item.packed_qty, 6)

		for item in dn.packed_items:
			self.assertEqual(item.packed_qty, 6)

		# Step - 6: Cancel Packing Slip [2]
		ps2.cancel()

		# Test - 4: `Packed Qty` should be updated to 0 in Delivery Note Items and Packed Items.
		dn.load_from_db()
		for item in dn.items:
			if not frappe.db.exists("Product Bundle", {"new_item_code": item.item_code}):
				self.assertEqual(item.packed_qty, 0)

		for item in dn.packed_items:
			self.assertEqual(item.packed_qty, 0)

		# Step - 7: Make Packing Slip for more Qty than Delivery Note
		ps3 = make_packing_slip(dn.name)
		ps3.items[0].qty = 20

		# Test - 5: Should throw an ValidationError, as Packing Slip Qty is more than Delivery Note Qty
		self.assertRaises(frappe.exceptions.ValidationError, ps3.save)

		# Step - 8: Make Packing Slip for less Qty than Delivery Note
		ps4 = make_packing_slip(dn.name)
		ps4.items[0].qty = 5
		ps4.save()
		ps4.submit()

		# Test - 6: Delivery Note should throw a ValidationError on Submit, as Packed Qty and Delivery Note Qty are not the same
		dn.load_from_db()
		self.assertRaises(frappe.exceptions.ValidationError, dn.submit)

	def test_validate_delivery_note_raises_on_non_draft_dn_TC_SCK_418(self):
		from erpnext.accounts.doctype.account.test_account import create_account
		from erpnext.stock.doctype.item.test_item import make_item
		from erpnext.stock.doctype.warehouse.test_warehouse import create_warehouse

		make_item(
			"_Test Item",
		)

		parent_expenses = frappe.db.get_value(
			"Account", {"account_name": "Expenses", "company": "_Test Company", "is_group": 1}, "name"
		)

		expense_account = create_account(
			account_name="Cost of Goods Sold",
			parent_account=parent_expenses,
			account_type="Expense",
			company="_Test Company",
			account_currency="INR",
		)

		# First, check if the group cost center exists
		parent_cost_center = frappe.db.get_value(
			"Cost Center", {"is_group": 1, "company": "_Test Company"}, "name"
		)

		# If not, create a group cost center
		if not parent_cost_center:
			parent_cost_center = (
				frappe.get_doc(
					{
						"doctype": "Cost Center",
						"cost_center_name": "_Test Parent CC",
						"company": "_Test Company",
						"is_group": 1,
					}
				)
				.insert(ignore_permissions=True)
				.name
			)

		cost_center = create_cost_center(
			cost_center_name="_Test Cost Center",
			parent_cost_center=parent_cost_center,
			company="_Test Company",
		)
		warehouse = create_warehouse("_Test Warehouse", company="_Test Company")

		# Step 1: Create and submit a Delivery Note (so docstatus = 1)
		dn = create_delivery_note(
			qty=1, warehouse=warehouse, cost_center=cost_center, expense_account=expense_account
		)
		dn.submit()

		# Step 2: Create Packing Slip linked to the submitted Delivery Note
		ps = frappe.new_doc("Packing Slip")
		ps.delivery_note = dn.name

		# Step 3: Call validate_delivery_note and expect ValidationError

		with self.assertRaises(frappe.ValidationError):
			ps.validate_delivery_note()

	def test_validate_case_nos_from_case_no_zero_TC_SCK_419(self):
		from erpnext.accounts.doctype.account.test_account import create_account
		from erpnext.stock.doctype.item.test_item import make_item
		from erpnext.stock.doctype.warehouse.test_warehouse import create_warehouse

		make_item(
			"_Test Item",
		)

		parent_expenses = frappe.db.get_value(
			"Account", {"account_name": "Expenses", "company": "_Test Company", "is_group": 1}, "name"
		)

		expense_account = create_account(
			account_name="Cost of Goods Sold",
			parent_account=parent_expenses,
			account_type="Expense",
			company="_Test Company",
			account_currency="INR",
		)

		# First, check if the group cost center exists
		parent_cost_center = frappe.db.get_value(
			"Cost Center", {"is_group": 1, "company": "_Test Company"}, "name"
		)

		# If not, create a group cost center
		if not parent_cost_center:
			parent_cost_center = (
				frappe.get_doc(
					{
						"doctype": "Cost Center",
						"cost_center_name": "_Test Parent CC",
						"company": "_Test Company",
						"is_group": 1,
					}
				)
				.insert(ignore_permissions=True)
				.name
			)

		cost_center = create_cost_center(
			cost_center_name="_Test Cost Center",
			parent_cost_center=parent_cost_center,
			company="_Test Company",
		)
		warehouse = create_warehouse("_Test Warehouse", company="_Test Company")

		# Step 1: Create and submit a Delivery Note (so docstatus = 1)
		self.dn = create_delivery_note(
			qty=1, warehouse=warehouse, cost_center=cost_center, expense_account=expense_account
		)
		ps = frappe.new_doc("Packing Slip")
		ps.delivery_note = self.dn.name
		ps.from_case_no = 0
		ps.to_case_no = 5

		with self.assertRaises(frappe.ValidationError, msg="Should raise if from_case_no <= 0"):
			ps.validate_case_nos()

	def test_validate_case_nos_to_less_than_from_TC_SCK_420(self):
		from erpnext.accounts.doctype.account.test_account import create_account
		from erpnext.stock.doctype.item.test_item import make_item
		from erpnext.stock.doctype.warehouse.test_warehouse import create_warehouse

		make_item(
			"_Test Item",
		)

		parent_expenses = frappe.db.get_value(
			"Account", {"account_name": "Expenses", "company": "_Test Company", "is_group": 1}, "name"
		)

		expense_account = create_account(
			account_name="Cost of Goods Sold",
			parent_account=parent_expenses,
			account_type="Expense",
			company="_Test Company",
			account_currency="INR",
		)

		# First, check if the group cost center exists
		parent_cost_center = frappe.db.get_value(
			"Cost Center", {"is_group": 1, "company": "_Test Company"}, "name"
		)

		# If not, create a group cost center
		if not parent_cost_center:
			parent_cost_center = (
				frappe.get_doc(
					{
						"doctype": "Cost Center",
						"cost_center_name": "_Test Parent CC",
						"company": "_Test Company",
						"is_group": 1,
					}
				)
				.insert(ignore_permissions=True)
				.name
			)

		cost_center = create_cost_center(
			cost_center_name="_Test Cost Center",
			parent_cost_center=parent_cost_center,
			company="_Test Company",
		)
		warehouse = create_warehouse("_Test Warehouse", company="_Test Company")

		# Step 1: Create and submit a Delivery Note (so docstatus = 1)
		self.dn = create_delivery_note(
			qty=1, warehouse=warehouse, cost_center=cost_center, expense_account=expense_account
		)
		ps = frappe.new_doc("Packing Slip")
		ps.delivery_note = self.dn.name
		ps.from_case_no = 10
		ps.to_case_no = 5

		with self.assertRaises(frappe.ValidationError, msg="Should raise if to_case_no < from_case_no"):
			ps.validate_case_nos()

	def test_calculate_net_total_pkg_raises_for_mismatched_uom_TC_SCK_422(self):
		# Create the test document
		ps = frappe.new_doc("Packing Slip")
		ps.delivery_note = "DN-TEST"

		# Add two items with different weight_uom
		ps.append("items", {"item_code": "_Test Item 1", "qty": 1, "net_weight": 2.5, "weight_uom": "Kg"})
		ps.append("items", {"item_code": "_Test Item 2", "qty": 1, "net_weight": 3.0, "weight_uom": "g"})

		# Assert that it throws the correct error
		with self.assertRaises(frappe.ValidationError, msg="Should raise error for different weight UOMs"):
			ps.calculate_net_total_pkg()

	def test_set_missing_values_sets_weight_fields_TC_SCK_423(self):
		from erpnext.stock.doctype.item.test_item import make_item
		from erpnext.stock.doctype.packing_slip.packing_slip import PackingSlip

		# Create item with defined weight attributes
		item_code = make_item(
			"_Test Item WGT", {"weight_per_unit": 2.0, "weight_uom": "Kg", "is_stock_item": 1}
		)

		# Create Packing Slip with item missing net_weight and weight_uom
		ps = frappe.new_doc("Packing Slip")
		ps.delivery_note = "DN-TEST"
		ps.append("items", {"item_code": item_code, "qty": 1, "net_weight": 0, "weight_uom": None})

		# Call method
		ps.set_missing_values()

		# Assertions to check if values were updated from Item master
		self.assertEqual(ps.items[0].net_weight, 2.0, msg="net_weight should be set from Item")
		self.assertEqual(ps.items[0].weight_uom, "Kg", msg="weight_uom should be set from Item")

	def test_validate_items_throws_for_invalid_qty_and_missing_references_TC_SCK_424(self):
		from erpnext.stock.doctype.packing_slip.packing_slip import PackingSlip

		# Create Packing Slip with invalid item
		ps = frappe.new_doc("Packing Slip")
		ps.delivery_note = "DN-TEST"

		ps.append(
			"items",
			{
				"item_code": "_Test Item",
				"qty": 0,  # Invalid qty
				"dn_detail": None,
				"pi_detail": None,
				"idx": 1,
			},
		)

		# Validate for qty <= 0
		with self.assertRaises(frappe.ValidationError, msg="Should raise error for qty <= 0"):
			ps.validate_items()

		# Fix qty, still missing reference
		ps.items[0].qty = 1
		with self.assertRaises(
			frappe.ValidationError, msg="Should raise error for missing dn_detail/pi_detail"
		):
			ps.validate_items()


def create_items():
	items_properties = [
		{"is_stock_item": 0},
		{"is_stock_item": 1, "stock_uom": "Nos"},
		{"is_stock_item": 1, "stock_uom": "Box"},
	]

	items = []
	for properties in items_properties:
		items.append(make_item(properties=properties).name)

	return items


def create_cost_center(**args):
	args = frappe._dict(args)
	if args.cost_center_name:
		company = args.company or "_Test Company"
		company_abbr = frappe.db.get_value("Company", company, "abbr")
		cc_name = args.cost_center_name + " - " + company_abbr
		if not frappe.db.exists("Cost Center", cc_name):
			cc = frappe.new_doc("Cost Center")
			cc.company = args.company or "_Test Company"
			cc.cost_center_name = args.cost_center_name
			cc.is_group = args.is_group or 0
			cc.parent_cost_center = args.parent_cost_center or "_Test Company - _TC"
			cc.insert()
		return cc_name
