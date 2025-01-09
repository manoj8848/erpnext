# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

import json

from erpnext.selling.doctype.customer.customer import get_customer_outstanding
import frappe
import frappe.permissions
from frappe.core.doctype.user_permission.test_user_permission import create_user
from frappe.tests.utils import FrappeTestCase, change_settings
from frappe.utils import add_days, flt, getdate, nowdate, today
from erpnext.stock.get_item_details import get_bin_details
from erpnext.accounts.test.accounts_mixin import AccountsTestMixin
from erpnext.controllers.accounts_controller import update_child_qty_rate
from erpnext.maintenance.doctype.maintenance_schedule.test_maintenance_schedule import (
	make_maintenance_schedule,
)
from erpnext.maintenance.doctype.maintenance_visit.test_maintenance_visit import (
	make_maintenance_visit,
)
from erpnext.manufacturing.doctype.blanket_order.test_blanket_order import make_blanket_order
from erpnext.selling.doctype.product_bundle.test_product_bundle import make_product_bundle
from erpnext.selling.doctype.sales_order.sales_order import (
	WarehouseRequired,
	create_pick_list,
	make_delivery_note,
	make_material_request,
	make_raw_material_request,
	make_sales_invoice,
	make_work_orders,
)
from erpnext.stock.doctype.item.test_item import make_item
from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry
from datetime import datetime


class TestSalesOrder(AccountsTestMixin, FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.unlink_setting = int(
			frappe.db.get_value(
				"Accounts Settings", "Accounts Settings", "unlink_advance_payment_on_cancelation_of_order"
			)
		)

	@classmethod
	def tearDownClass(cls) -> None:
		# reset config to previous state
		frappe.db.set_single_value(
			"Accounts Settings", "unlink_advance_payment_on_cancelation_of_order", cls.unlink_setting
		)
		super().tearDownClass()

	def setUp(self):
		self.create_customer("_Test Customer Credit")

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_sales_order_with_negative_rate(self):
		"""
		Test if negative rate is allowed in Sales Order via doc submission and update items
		"""
		so = make_sales_order(qty=1, rate=100, do_not_save=True)
		so.append("items", {"item_code": "_Test Item", "qty": 1, "rate": -10})
		so.save()
		so.submit()

		first_item = so.get("items")[0]
		second_item = so.get("items")[1]
		trans_item = json.dumps(
			[
				{
					"item_code": first_item.item_code,
					"rate": first_item.rate,
					"qty": first_item.qty,
					"docname": first_item.name,
				},
				{
					"item_code": second_item.item_code,
					"rate": -20,
					"qty": second_item.qty,
					"docname": second_item.name,
				},
			]
		)
		update_child_qty_rate("Sales Order", trans_item, so.name)

	def test_make_material_request(self):
		so = make_sales_order(do_not_submit=True)

		self.assertRaises(frappe.ValidationError, make_material_request, so.name)

		so.submit()
		mr = make_material_request(so.name)

		self.assertEqual(mr.material_request_type, "Purchase")
		self.assertEqual(len(mr.get("items")), len(so.get("items")))

		for item in mr.get("items"):
			actual_qty = get_bin_details(item.item_code, item.warehouse, mr.company, True).get(
				"actual_qty", 0
			)
			self.assertEqual(flt(item.actual_qty), actual_qty)

	def test_make_delivery_note(self):
		so = make_sales_order(do_not_submit=True)

		self.assertRaises(frappe.ValidationError, make_delivery_note, so.name)

		so.submit()
		dn = make_delivery_note(so.name)

		self.assertEqual(dn.doctype, "Delivery Note")
		self.assertEqual(len(dn.get("items")), len(so.get("items")))

	def test_make_sales_invoice(self):
		so = make_sales_order(do_not_submit=True)

		self.assertRaises(frappe.ValidationError, make_sales_invoice, so.name)

		so.submit()
		si = make_sales_invoice(so.name)

		self.assertEqual(len(si.get("items")), len(so.get("items")))
		self.assertEqual(len(si.get("items")), 1)

		si.insert()
		si.submit()

		si1 = make_sales_invoice(so.name)
		self.assertEqual(len(si1.get("items")), 0)

	def test_so_billed_amount_against_return_entry(self):
		from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_sales_return

		so = make_sales_order(do_not_submit=True)
		so.submit()

		si = make_sales_invoice(so.name)
		si.insert()
		si.submit()

		si1 = make_sales_return(si.name)
		si1.update_billed_amount_in_sales_order = 1
		si1.submit()
		so.load_from_db()
		self.assertEqual(so.per_billed, 0)

	def test_make_sales_invoice_with_terms(self):
		so = make_sales_order(do_not_submit=True)

		self.assertRaises(frappe.ValidationError, make_sales_invoice, so.name)

		so.update({"payment_terms_template": "_Test Payment Term Template"})

		so.save()
		so.submit()
		si = make_sales_invoice(so.name)

		self.assertEqual(len(si.get("items")), len(so.get("items")))
		self.assertEqual(len(si.get("items")), 1)

		si.insert()
		si.set("taxes", [])
		si.save()

		transaction_date = datetime.strptime(so.transaction_date, "%Y-%m-%d").date()
		self.assertEqual(si.payment_schedule[0].payment_amount, 500.0)
		self.assertEqual(si.payment_schedule[0].due_date, transaction_date)
		self.assertEqual(si.payment_schedule[1].payment_amount, 500.0)
		self.assertEqual(si.payment_schedule[1].due_date, add_days(transaction_date, 30))

		si.submit()

		si1 = make_sales_invoice(so.name)
		self.assertEqual(len(si1.get("items")), 0)

	def test_update_qty(self):
		so = make_sales_order()

		create_dn_against_so(so.name, 6)

		so.load_from_db()
		self.assertEqual(so.get("items")[0].delivered_qty, 6)

		# Check delivered_qty after make_sales_invoice without update_stock checked
		si1 = make_sales_invoice(so.name)
		si1.get("items")[0].qty = 6
		si1.insert()
		si1.submit()

		so.load_from_db()
		self.assertEqual(so.get("items")[0].delivered_qty, 6)

		# Check delivered_qty after make_sales_invoice with update_stock checked
		si2 = make_sales_invoice(so.name)
		si2.set("update_stock", 1)
		si2.get("items")[0].qty = 3
		si2.insert()
		si2.submit()

		so.load_from_db()
		self.assertEqual(so.get("items")[0].delivered_qty, 9)

	def test_return_against_sales_order(self):
		so = make_sales_order()

		dn = create_dn_against_so(so.name, 6)

		so.load_from_db()
		self.assertEqual(so.get("items")[0].delivered_qty, 6)

		# Check delivered_qty after make_sales_invoice with update_stock checked
		si2 = make_sales_invoice(so.name)
		si2.set("update_stock", 1)
		si2.get("items")[0].qty = 3
		si2.insert()
		si2.submit()

		so.load_from_db()

		self.assertEqual(so.get("items")[0].delivered_qty, 9)

		# Make return deliver note, sales invoice and check quantity
		from erpnext.accounts.doctype.sales_invoice.test_sales_invoice import create_sales_invoice
		from erpnext.stock.doctype.delivery_note.test_delivery_note import create_delivery_note

		dn1 = create_delivery_note(is_return=1, return_against=dn.name, qty=-3, do_not_submit=True)
		dn1.items[0].against_sales_order = so.name
		dn1.items[0].so_detail = so.items[0].name
		dn1.submit()

		si1 = create_sales_invoice(
			is_return=1, return_against=si2.name, qty=-1, update_stock=1, do_not_submit=True
		)
		si1.items[0].sales_order = so.name
		si1.items[0].so_detail = so.items[0].name
		si1.submit()

		so.load_from_db()
		self.assertEqual(so.get("items")[0].delivered_qty, 5)

	def test_reserved_qty_for_partial_delivery(self):
		make_stock_entry(target="_Test Warehouse - _TC", qty=10, rate=100)
		existing_reserved_qty = get_reserved_qty()

		so = make_sales_order()
		self.assertEqual(get_reserved_qty(), existing_reserved_qty + 10)

		dn = create_dn_against_so(so.name)
		self.assertEqual(get_reserved_qty(), existing_reserved_qty + 5)

		# close so
		so.load_from_db()
		so.update_status("Closed")
		self.assertEqual(get_reserved_qty(), existing_reserved_qty)

		# unclose so
		so.load_from_db()
		so.update_status("Draft")
		self.assertEqual(get_reserved_qty(), existing_reserved_qty + 5)

		dn.cancel()
		self.assertEqual(get_reserved_qty(), existing_reserved_qty + 10)

		# cancel
		so.load_from_db()
		so.cancel()
		self.assertEqual(get_reserved_qty(), existing_reserved_qty)

	def test_reserved_qty_for_over_delivery(self):
		make_stock_entry(target="_Test Warehouse - _TC", qty=10, rate=100)
		# set over-delivery allowance
		frappe.db.set_value("Item", "_Test Item", "over_delivery_receipt_allowance", 50)

		existing_reserved_qty = get_reserved_qty()

		so = make_sales_order()
		self.assertEqual(get_reserved_qty(), existing_reserved_qty + 10)

		dn = create_dn_against_so(so.name, 15)
		self.assertEqual(get_reserved_qty(), existing_reserved_qty)

		dn.cancel()
		self.assertEqual(get_reserved_qty(), existing_reserved_qty + 10)

	def test_reserved_qty_for_over_delivery_via_sales_invoice(self):
		make_stock_entry(target="_Test Warehouse - _TC", qty=10, rate=100)

		# set over-delivery allowance
		frappe.db.set_value("Item", "_Test Item", "over_delivery_receipt_allowance", 50)
		frappe.db.set_value("Item", "_Test Item", "over_billing_allowance", 20)

		existing_reserved_qty = get_reserved_qty()

		so = make_sales_order()
		self.assertEqual(get_reserved_qty(), existing_reserved_qty + 10)

		si = make_sales_invoice(so.name)
		si.update_stock = 1
		si.get("items")[0].qty = 12
		si.insert()
		si.submit()

		self.assertEqual(get_reserved_qty(), existing_reserved_qty)

		so.load_from_db()
		self.assertEqual(so.get("items")[0].delivered_qty, 12)
		self.assertEqual(so.per_delivered, 100)

		si.cancel()
		self.assertEqual(get_reserved_qty(), existing_reserved_qty + 10)

		so.load_from_db()
		self.assertEqual(so.get("items")[0].delivered_qty, 0)
		self.assertEqual(so.per_delivered, 0)

	def test_reserved_qty_for_partial_delivery_with_packing_list(self):
		make_stock_entry(target="_Test Warehouse - _TC", qty=10, rate=100)
		make_stock_entry(item="_Test Item Home Desktop 100", target="_Test Warehouse - _TC", qty=10, rate=100)

		existing_reserved_qty_item1 = get_reserved_qty("_Test Item")
		existing_reserved_qty_item2 = get_reserved_qty("_Test Item Home Desktop 100")

		so = make_sales_order(item_code="_Test Product Bundle Item")

		self.assertEqual(get_reserved_qty("_Test Item"), existing_reserved_qty_item1 + 50)
		self.assertEqual(get_reserved_qty("_Test Item Home Desktop 100"), existing_reserved_qty_item2 + 20)

		dn = create_dn_against_so(so.name)

		self.assertEqual(get_reserved_qty("_Test Item"), existing_reserved_qty_item1 + 25)
		self.assertEqual(get_reserved_qty("_Test Item Home Desktop 100"), existing_reserved_qty_item2 + 10)

		# close so
		so.load_from_db()
		so.update_status("Closed")

		self.assertEqual(get_reserved_qty("_Test Item"), existing_reserved_qty_item1)
		self.assertEqual(get_reserved_qty("_Test Item Home Desktop 100"), existing_reserved_qty_item2)

		# unclose so
		so.load_from_db()
		so.update_status("Draft")

		self.assertEqual(get_reserved_qty("_Test Item"), existing_reserved_qty_item1 + 25)
		self.assertEqual(get_reserved_qty("_Test Item Home Desktop 100"), existing_reserved_qty_item2 + 10)

		dn.cancel()
		self.assertEqual(get_reserved_qty("_Test Item"), existing_reserved_qty_item1 + 50)
		self.assertEqual(get_reserved_qty("_Test Item Home Desktop 100"), existing_reserved_qty_item2 + 20)

		so.load_from_db()
		so.cancel()
		self.assertEqual(get_reserved_qty("_Test Item"), existing_reserved_qty_item1)
		self.assertEqual(get_reserved_qty("_Test Item Home Desktop 100"), existing_reserved_qty_item2)

	def test_sales_order_on_hold(self):
		so = make_sales_order(item_code="_Test Product Bundle Item")
		so.db_set("status", "On Hold")
		si = make_sales_invoice(so.name)
		self.assertRaises(frappe.ValidationError, create_dn_against_so, so.name)
		self.assertRaises(frappe.ValidationError, si.submit)

	def test_reserved_qty_for_over_delivery_with_packing_list(self):
		make_stock_entry(target="_Test Warehouse - _TC", qty=10, rate=100)
		make_stock_entry(item="_Test Item Home Desktop 100", target="_Test Warehouse - _TC", qty=10, rate=100)

		# set over-delivery allowance
		frappe.db.set_value("Item", "_Test Product Bundle Item", "over_delivery_receipt_allowance", 50)

		existing_reserved_qty_item1 = get_reserved_qty("_Test Item")
		existing_reserved_qty_item2 = get_reserved_qty("_Test Item Home Desktop 100")

		so = make_sales_order(item_code="_Test Product Bundle Item")

		self.assertEqual(get_reserved_qty("_Test Item"), existing_reserved_qty_item1 + 50)
		self.assertEqual(get_reserved_qty("_Test Item Home Desktop 100"), existing_reserved_qty_item2 + 20)

		dn = create_dn_against_so(so.name, 15)

		self.assertEqual(get_reserved_qty("_Test Item"), existing_reserved_qty_item1)
		self.assertEqual(get_reserved_qty("_Test Item Home Desktop 100"), existing_reserved_qty_item2)

		dn.cancel()
		self.assertEqual(get_reserved_qty("_Test Item"), existing_reserved_qty_item1 + 50)
		self.assertEqual(get_reserved_qty("_Test Item Home Desktop 100"), existing_reserved_qty_item2 + 20)

	def test_update_child_adding_new_item(self):
		so = make_sales_order(item_code="_Test Item", qty=4)
		create_dn_against_so(so.name, 4)
		make_sales_invoice(so.name)

		prev_total = so.get("base_total")
		prev_total_in_words = so.get("base_in_words")

		# get reserved qty before update items
		reserved_qty_for_second_item = get_reserved_qty("_Test Item 2")

		first_item_of_so = so.get("items")[0]
		trans_item = json.dumps(
			[
				{
					"item_code": first_item_of_so.item_code,
					"rate": first_item_of_so.rate,
					"qty": first_item_of_so.qty,
					"docname": first_item_of_so.name,
				},
				{"item_code": "_Test Item 2", "rate": 200, "qty": 7},
			]
		)
		update_child_qty_rate("Sales Order", trans_item, so.name)

		so.reload()
		self.assertEqual(so.get("items")[-1].item_code, "_Test Item 2")
		self.assertEqual(so.get("items")[-1].rate, 200)
		self.assertEqual(so.get("items")[-1].qty, 7)
		self.assertEqual(so.get("items")[-1].amount, 1400)

		# reserved qty should increase after adding row
		self.assertEqual(get_reserved_qty("_Test Item 2"), reserved_qty_for_second_item + 7)

		self.assertEqual(so.status, "To Deliver and Bill")

		updated_total = so.get("base_total")
		updated_total_in_words = so.get("base_in_words")

		self.assertEqual(updated_total, prev_total + 1400)
		self.assertNotEqual(updated_total_in_words, prev_total_in_words)

	def test_update_child_removing_item(self):
		so = make_sales_order(**{"item_list": [{"item_code": "_Test Item", "qty": 5, "rate": 1000}]})
		create_dn_against_so(so.name, 2)
		make_sales_invoice(so.name)

		# get reserved qty before update items
		reserved_qty_for_second_item = get_reserved_qty("_Test Item 2")

		# add an item so as to try removing items
		trans_item = json.dumps(
			[
				{"item_code": "_Test Item", "qty": 5, "rate": 1000, "docname": so.get("items")[0].name},
				{"item_code": "_Test Item 2", "qty": 2, "rate": 500},
			]
		)
		update_child_qty_rate("Sales Order", trans_item, so.name)
		so.reload()
		self.assertEqual(len(so.get("items")), 2)

		# reserved qty should increase after adding row
		self.assertEqual(get_reserved_qty("_Test Item 2"), reserved_qty_for_second_item + 2)

		# check if delivered items can be removed
		trans_item = json.dumps(
			[{"item_code": "_Test Item 2", "qty": 2, "rate": 500, "docname": so.get("items")[1].name}]
		)
		self.assertRaises(frappe.ValidationError, update_child_qty_rate, "Sales Order", trans_item, so.name)

		# remove last added item
		trans_item = json.dumps(
			[{"item_code": "_Test Item", "qty": 5, "rate": 1000, "docname": so.get("items")[0].name}]
		)
		update_child_qty_rate("Sales Order", trans_item, so.name)

		so.reload()
		self.assertEqual(len(so.get("items")), 1)

		# reserved qty should decrease (back to initial) after deleting row
		self.assertEqual(get_reserved_qty("_Test Item 2"), reserved_qty_for_second_item)

		self.assertEqual(so.status, "To Deliver and Bill")

	def test_update_child(self):
		so = make_sales_order(item_code="_Test Item", qty=4)
		create_dn_against_so(so.name, 4)
		make_sales_invoice(so.name)

		existing_reserved_qty = get_reserved_qty()

		trans_item = json.dumps(
			[{"item_code": "_Test Item", "rate": 200, "qty": 7, "docname": so.items[0].name}]
		)
		update_child_qty_rate("Sales Order", trans_item, so.name)

		so.reload()
		self.assertEqual(so.get("items")[0].rate, 200)
		self.assertEqual(so.get("items")[0].qty, 7)
		self.assertEqual(so.get("items")[0].amount, 1400)
		self.assertEqual(so.status, "To Deliver and Bill")

		self.assertEqual(get_reserved_qty(), existing_reserved_qty + 3)

		trans_item = json.dumps(
			[{"item_code": "_Test Item", "rate": 200, "qty": 2, "docname": so.items[0].name}]
		)
		self.assertRaises(frappe.ValidationError, update_child_qty_rate, "Sales Order", trans_item, so.name)

	def test_update_child_with_precision(self):
		from frappe.custom.doctype.property_setter.property_setter import make_property_setter
		from frappe.model.meta import get_field_precision

		precision = get_field_precision(frappe.get_meta("Sales Order Item").get_field("rate"))

		make_property_setter("Sales Order Item", "rate", "precision", 7, "Currency")
		so = make_sales_order(item_code="_Test Item", qty=4, rate=200.34664)

		trans_item = json.dumps(
			[{"item_code": "_Test Item", "rate": 200.34669, "qty": 4, "docname": so.items[0].name}]
		)
		update_child_qty_rate("Sales Order", trans_item, so.name)

		so.reload()
		self.assertEqual(so.items[0].rate, 200.34669)
		make_property_setter("Sales Order Item", "rate", "precision", precision, "Currency")

	def test_update_child_perm(self):
		so = make_sales_order(item_code="_Test Item", qty=4)

		test_user = create_user("test_so_child_perms@example.com", "Accounts User")
		frappe.set_user(test_user.name)

		# update qty
		trans_item = json.dumps(
			[{"item_code": "_Test Item", "rate": 200, "qty": 7, "docname": so.items[0].name}]
		)
		self.assertRaises(frappe.ValidationError, update_child_qty_rate, "Sales Order", trans_item, so.name)

		# add new item
		trans_item = json.dumps([{"item_code": "_Test Item", "rate": 100, "qty": 2}])
		self.assertRaises(frappe.ValidationError, update_child_qty_rate, "Sales Order", trans_item, so.name)

	def test_update_child_qty_rate_with_workflow(self):
		from frappe.model.workflow import apply_workflow

		workflow = make_sales_order_workflow()
		so = make_sales_order(item_code="_Test Item", qty=1, rate=150, do_not_submit=1)
		apply_workflow(so, "Approve")

		user = "test@example.com"
		test_user = frappe.get_doc("User", user)
		test_user.add_roles("Sales User", "Test Junior Approver")
		frappe.set_user(user)

		# user shouldn't be able to edit since grand_total will become > 200 if qty is doubled
		trans_item = json.dumps(
			[{"item_code": "_Test Item", "rate": 150, "qty": 2, "docname": so.items[0].name}]
		)
		self.assertRaises(frappe.ValidationError, update_child_qty_rate, "Sales Order", trans_item, so.name)

		frappe.set_user("Administrator")
		user2 = "test2@example.com"
		test_user2 = frappe.get_doc("User", user2)
		test_user2.add_roles("Sales User", "Test Approver")
		frappe.set_user(user2)

		# Test Approver is allowed to edit with grand_total > 200
		update_child_qty_rate("Sales Order", trans_item, so.name)
		so.reload()
		self.assertEqual(so.items[0].qty, 2)

		frappe.set_user("Administrator")
		test_user.remove_roles("Sales User", "Test Junior Approver", "Test Approver")
		test_user2.remove_roles("Sales User", "Test Junior Approver", "Test Approver")
		workflow.is_active = 0
		workflow.save()

	def test_material_request_for_product_bundle(self):
		# Create the Material Request from the sales order for the Packing Items
		# Check whether the material request has the correct packing item or not.
		if not frappe.db.exists("Item", "_Test Product Bundle Item New 1"):
			bundle_item = make_item("_Test Product Bundle Item New 1", {"is_stock_item": 0})
			bundle_item.append(
				"item_defaults", {"company": "_Test Company", "default_warehouse": "_Test Warehouse - _TC"}
			)
			bundle_item.save(ignore_permissions=True)

		make_item("_Packed Item New 2", {"is_stock_item": 1})
		make_product_bundle("_Test Product Bundle Item New 1", ["_Packed Item New 2"], 2)

		so = make_sales_order(
			item_code="_Test Product Bundle Item New 1",
		)

		mr = make_material_request(so.name)
		self.assertEqual(mr.items[0].item_code, "_Packed Item New 2")

	def test_bin_details_of_packed_item(self):
		# test Update Items with product bundle
		if not frappe.db.exists("Item", "_Test Product Bundle Item New"):
			bundle_item = make_item("_Test Product Bundle Item New", {"is_stock_item": 0})
			bundle_item.append(
				"item_defaults", {"company": "_Test Company", "default_warehouse": "_Test Warehouse - _TC"}
			)
			bundle_item.save(ignore_permissions=True)

		make_item("_Packed Item New 1", {"is_stock_item": 1})
		make_product_bundle("_Test Product Bundle Item New", ["_Packed Item New 1"], 2)

		so = make_sales_order(
			item_code="_Test Product Bundle Item New",
			warehouse="_Test Warehouse - _TC",
			transaction_date=add_days(nowdate(), -1),
			do_not_submit=1,
		)

		make_stock_entry(item="_Packed Item New 1", target="_Test Warehouse - _TC", qty=120, rate=100)

		bin_details = frappe.db.get_value(
			"Bin",
			{"item_code": "_Packed Item New 1", "warehouse": "_Test Warehouse - _TC"},
			["actual_qty", "projected_qty", "ordered_qty"],
			as_dict=1,
		)

		so.transaction_date = nowdate()
		so.save()

		packed_item = so.packed_items[0]
		self.assertEqual(flt(bin_details.actual_qty), flt(packed_item.actual_qty))
		self.assertEqual(flt(bin_details.projected_qty), flt(packed_item.projected_qty))
		self.assertEqual(flt(bin_details.ordered_qty), flt(packed_item.ordered_qty))

	def test_update_child_product_bundle(self):
		# test Update Items with product bundle
		if not frappe.db.exists("Item", "_Product Bundle Item"):
			bundle_item = make_item("_Product Bundle Item", {"is_stock_item": 0})
			bundle_item.append(
				"item_defaults", {"company": "_Test Company", "default_warehouse": "_Test Warehouse - _TC"}
			)
			bundle_item.save(ignore_permissions=True)

		make_item("_Packed Item", {"is_stock_item": 1})
		make_product_bundle("_Product Bundle Item", ["_Packed Item"], 2)

		so = make_sales_order(item_code="_Test Item", warehouse=None)

		# get reserved qty of packed item
		existing_reserved_qty = get_reserved_qty("_Packed Item")

		added_item = json.dumps([{"item_code": "_Product Bundle Item", "rate": 200, "qty": 2}])
		update_child_qty_rate("Sales Order", added_item, so.name)

		so.reload()
		self.assertEqual(so.packed_items[0].qty, 4)

		# reserved qty in packed item should increase after adding bundle item
		self.assertEqual(get_reserved_qty("_Packed Item"), existing_reserved_qty + 4)

		# test uom and conversion factor change
		update_uom_conv_factor = json.dumps(
			[
				{
					"item_code": so.get("items")[0].item_code,
					"rate": so.get("items")[0].rate,
					"qty": so.get("items")[0].qty,
					"uom": "_Test UOM 1",
					"conversion_factor": 2,
					"docname": so.get("items")[0].name,
				}
			]
		)
		update_child_qty_rate("Sales Order", update_uom_conv_factor, so.name)

		so.reload()
		self.assertEqual(so.packed_items[0].qty, 8)

		# reserved qty in packed item should increase after changing bundle item uom
		self.assertEqual(get_reserved_qty("_Packed Item"), existing_reserved_qty + 8)

	def test_update_child_with_tax_template(self):
		"""
		Test Action: Create a SO with one item having its tax account head already in the SO.
		Add the same item + new item with tax template via Update Items.
		Expected result: First Item's tax row is updated. New tax row is added for second Item.
		"""
		if not frappe.db.exists("Item", "Test Item with Tax"):
			make_item(
				"Test Item with Tax",
				{
					"is_stock_item": 1,
				},
			)

		if not frappe.db.exists("Item Tax Template", {"title": "Test Update Items Template"}):
			frappe.get_doc(
				{
					"doctype": "Item Tax Template",
					"title": "Test Update Items Template",
					"company": "_Test Company",
					"taxes": [
						{
							"tax_type": "_Test Account Service Tax - _TC",
							"tax_rate": 10,
						}
					],
				}
			).insert()

		new_item_with_tax = frappe.get_doc("Item", "Test Item with Tax")

		new_item_with_tax.append(
			"taxes", {"item_tax_template": "Test Update Items Template - _TC", "valid_from": nowdate()}
		)
		new_item_with_tax.save()

		tax_template = "_Test Account Excise Duty @ 10 - _TC"
		item = "_Test Item Home Desktop 100"
		if not frappe.db.exists("Item Tax", {"parent": item, "item_tax_template": tax_template}):
			item_doc = frappe.get_doc("Item", item)
			item_doc.append("taxes", {"item_tax_template": tax_template, "valid_from": nowdate()})
			item_doc.save()
		else:
			# update valid from
			frappe.db.sql(
				"""UPDATE `tabItem Tax` set valid_from = CURRENT_DATE
				where parent = %(item)s and item_tax_template = %(tax)s""",
				{"item": item, "tax": tax_template},
			)

		so = make_sales_order(item_code=item, qty=1, do_not_save=1)

		so.append(
			"taxes",
			{
				"account_head": "_Test Account Excise Duty - _TC",
				"charge_type": "On Net Total",
				"cost_center": "_Test Cost Center - _TC",
				"description": "Excise Duty",
				"doctype": "Sales Taxes and Charges",
				"rate": 10,
			},
		)
		so.insert()
		so.submit()

		self.assertEqual(so.taxes[0].tax_amount, 10)
		self.assertEqual(so.taxes[0].total, 110)

		old_stock_settings_value = frappe.db.get_single_value("Stock Settings", "default_warehouse")
		frappe.db.set_single_value("Stock Settings", "default_warehouse", "_Test Warehouse - _TC")

		items = json.dumps(
			[
				{"item_code": item, "rate": 100, "qty": 1, "docname": so.items[0].name},
				{
					"item_code": item,
					"rate": 200,
					"qty": 1,
				},  # added item whose tax account head already exists in PO
				{
					"item_code": new_item_with_tax.name,
					"rate": 100,
					"qty": 1,
				},  # added item whose tax account head  is missing in PO
			]
		)
		update_child_qty_rate("Sales Order", items, so.name)

		so.reload()
		self.assertEqual(so.taxes[0].tax_amount, 40)
		self.assertEqual(so.taxes[0].total, 440)
		self.assertEqual(so.taxes[1].account_head, "_Test Account Service Tax - _TC")
		self.assertEqual(so.taxes[1].tax_amount, 40)
		self.assertEqual(so.taxes[1].total, 480)

		# teardown
		frappe.db.sql(
			"""UPDATE `tabItem Tax` set valid_from = NULL
			where parent = %(item)s and item_tax_template = %(tax)s""",
			{"item": item, "tax": tax_template},
		)
		so.cancel()
		so.delete()
		new_item_with_tax.delete()
		frappe.get_doc("Item Tax Template", "Test Update Items Template - _TC").delete()
		frappe.db.set_single_value("Stock Settings", "default_warehouse", old_stock_settings_value)

	def test_warehouse_user(self):
		test_user = create_user("test_so_warehouse_user@example.com", "Sales User", "Stock User")

		test_user_2 = frappe.get_doc("User", "test2@example.com")
		test_user_2.add_roles("Sales User", "Stock User")
		test_user_2.remove_roles("Sales Manager")

		frappe.permissions.add_user_permission("Warehouse", "_Test Warehouse 1 - _TC", test_user.name)
		frappe.permissions.add_user_permission("Warehouse", "_Test Warehouse 2 - _TC1", test_user_2.name)
		frappe.permissions.add_user_permission("Company", "_Test Company 1", test_user_2.name)

		frappe.set_user(test_user.name)

		so = make_sales_order(
			company="_Test Company 1",
			customer="_Test Customer 1",
			warehouse="_Test Warehouse 2 - _TC1",
			do_not_save=True,
		)
		so.conversion_rate = 0.02
		so.plc_conversion_rate = 0.02
		self.assertRaises(frappe.PermissionError, so.insert)

		frappe.set_user(test_user_2.name)
		so.insert()

		frappe.set_user("Administrator")
		frappe.permissions.remove_user_permission("Warehouse", "_Test Warehouse 1 - _TC", test_user.name)
		frappe.permissions.remove_user_permission("Warehouse", "_Test Warehouse 2 - _TC1", test_user_2.name)
		frappe.permissions.remove_user_permission("Company", "_Test Company 1", test_user_2.name)

	def test_block_delivery_note_against_cancelled_sales_order(self):
		so = make_sales_order()

		dn = make_delivery_note(so.name)
		dn.insert()

		so.cancel()

		dn.load_from_db()

		self.assertRaises(frappe.CancelledLinkError, dn.submit)

	def test_service_type_product_bundle(self):
		make_item("_Test Service Product Bundle", {"is_stock_item": 0})
		make_item("_Test Service Product Bundle Item 1", {"is_stock_item": 0})
		make_item("_Test Service Product Bundle Item 2", {"is_stock_item": 0})

		make_product_bundle(
			"_Test Service Product Bundle",
			["_Test Service Product Bundle Item 1", "_Test Service Product Bundle Item 2"],
		)

		so = make_sales_order(item_code="_Test Service Product Bundle", warehouse=None)

		self.assertTrue("_Test Service Product Bundle Item 1" in [d.item_code for d in so.packed_items])
		self.assertTrue("_Test Service Product Bundle Item 2" in [d.item_code for d in so.packed_items])

	def test_mix_type_product_bundle(self):
		make_item("_Test Mix Product Bundle", {"is_stock_item": 0})
		make_item("_Test Mix Product Bundle Item 1", {"is_stock_item": 1})
		make_item("_Test Mix Product Bundle Item 2", {"is_stock_item": 0})

		make_product_bundle(
			"_Test Mix Product Bundle",
			["_Test Mix Product Bundle Item 1", "_Test Mix Product Bundle Item 2"],
		)

		self.assertRaises(
			WarehouseRequired, make_sales_order, item_code="_Test Mix Product Bundle", warehouse=""
		)

	def test_auto_insert_price(self):
		make_item("_Test Item for Auto Price List", {"is_stock_item": 0})
		make_item("_Test Item for Auto Price List with Discount Percentage", {"is_stock_item": 0})
		frappe.db.set_single_value("Stock Settings", "auto_insert_price_list_rate_if_missing", 1)

		item_price = frappe.db.get_value(
			"Item Price", {"price_list": "_Test Price List", "item_code": "_Test Item for Auto Price List"}
		)
		if item_price:
			frappe.delete_doc("Item Price", item_price)

		make_sales_order(
			item_code="_Test Item for Auto Price List", selling_price_list="_Test Price List", rate=100
		)

		self.assertEqual(
			frappe.db.get_value(
				"Item Price",
				{"price_list": "_Test Price List", "item_code": "_Test Item for Auto Price List"},
				"price_list_rate",
			),
			100,
		)

		make_sales_order(
			item_code="_Test Item for Auto Price List with Discount Percentage",
			selling_price_list="_Test Price List",
			price_list_rate=200,
			discount_percentage=20,
		)

		self.assertEqual(
			frappe.db.get_value(
				"Item Price",
				{
					"price_list": "_Test Price List",
					"item_code": "_Test Item for Auto Price List with Discount Percentage",
				},
				"price_list_rate",
			),
			200,
		)

		# do not update price list
		frappe.db.set_single_value("Stock Settings", "auto_insert_price_list_rate_if_missing", 0)

		item_price = frappe.db.get_value(
			"Item Price", {"price_list": "_Test Price List", "item_code": "_Test Item for Auto Price List"}
		)
		if item_price:
			frappe.delete_doc("Item Price", item_price)

		make_sales_order(
			item_code="_Test Item for Auto Price List", selling_price_list="_Test Price List", rate=100
		)

		self.assertEqual(
			frappe.db.get_value(
				"Item Price",
				{"price_list": "_Test Price List", "item_code": "_Test Item for Auto Price List"},
				"price_list_rate",
			),
			None,
		)

		frappe.db.set_single_value("Stock Settings", "auto_insert_price_list_rate_if_missing", 1)

	def test_drop_shipping(self):
		from erpnext.buying.doctype.purchase_order.purchase_order import update_status
		from erpnext.selling.doctype.sales_order.sales_order import (
			make_purchase_order_for_default_supplier,
		)
		from erpnext.selling.doctype.sales_order.sales_order import update_status as so_update_status

		# make items
		po_item = make_item("_Test Item for Drop Shipping", {"is_stock_item": 1, "delivered_by_supplier": 1})
		dn_item = make_item("_Test Regular Item", {"is_stock_item": 1})

		so_items = [
			{
				"item_code": po_item.item_code,
				"warehouse": "",
				"qty": 2,
				"rate": 400,
				"delivered_by_supplier": 1,
				"supplier": "_Test Supplier",
			},
			{
				"item_code": dn_item.item_code,
				"warehouse": "_Test Warehouse - _TC",
				"qty": 2,
				"rate": 300,
				"conversion_factor": 1.0,
			},
		]

		if frappe.db.get_value("Item", "_Test Regular Item", "is_stock_item") == 1:
			make_stock_entry(item="_Test Regular Item", target="_Test Warehouse - _TC", qty=2, rate=100)

		# create so, po and dn
		so = make_sales_order(item_list=so_items, do_not_submit=True)
		so.submit()

		po = make_purchase_order_for_default_supplier(so.name, selected_items=[so_items[0]])[0]
		po.submit()

		dn = create_dn_against_so(so.name, delivered_qty=2)

		self.assertEqual(so.customer, po.customer)
		self.assertEqual(po.items[0].sales_order, so.name)
		self.assertEqual(po.items[0].item_code, po_item.item_code)
		self.assertEqual(dn.items[0].item_code, dn_item.item_code)
		# test po_item length
		self.assertEqual(len(po.items), 1)

		# test ordered_qty and reserved_qty for drop ship item
		bin_po_item = frappe.get_all(
			"Bin",
			filters={"item_code": po_item.item_code, "warehouse": "_Test Warehouse - _TC"},
			fields=["ordered_qty", "reserved_qty"],
		)

		ordered_qty = bin_po_item[0].ordered_qty if bin_po_item else 0.0
		reserved_qty = bin_po_item[0].reserved_qty if bin_po_item else 0.0

		# drop ship PO should not impact bin, test the same
		self.assertEqual(abs(flt(ordered_qty)), 0)
		self.assertEqual(abs(flt(reserved_qty)), 0)

		# test per_delivered status
		update_status("Delivered", po.name)
		self.assertEqual(flt(frappe.db.get_value("Sales Order", so.name, "per_delivered"), 2), 100.00)
		po.load_from_db()

		# test after closing so
		so.db_set("status", "Closed")
		so.update_reserved_qty()

		# test ordered_qty and reserved_qty for drop ship item after closing so
		bin_po_item = frappe.get_all(
			"Bin",
			filters={"item_code": po_item.item_code, "warehouse": "_Test Warehouse - _TC"},
			fields=["ordered_qty", "reserved_qty"],
		)

		ordered_qty = bin_po_item[0].ordered_qty if bin_po_item else 0.0
		reserved_qty = bin_po_item[0].reserved_qty if bin_po_item else 0.0

		self.assertEqual(abs(flt(ordered_qty)), 0)
		self.assertEqual(abs(flt(reserved_qty)), 0)

		# teardown
		so_update_status("Draft", so.name)
		dn.load_from_db()
		dn.cancel()
		po.cancel()
		so.load_from_db()
		so.cancel()

	def test_drop_shipping_partial_order(self):
		from erpnext.selling.doctype.sales_order.sales_order import (
			make_purchase_order_for_default_supplier,
		)
		from erpnext.selling.doctype.sales_order.sales_order import update_status as so_update_status

		# make items
		po_item1 = make_item(
			"_Test Item for Drop Shipping 1", {"is_stock_item": 1, "delivered_by_supplier": 1}
		)
		po_item2 = make_item(
			"_Test Item for Drop Shipping 2", {"is_stock_item": 1, "delivered_by_supplier": 1}
		)

		so_items = [
			{
				"item_code": po_item1.item_code,
				"warehouse": "",
				"qty": 2,
				"rate": 400,
				"delivered_by_supplier": 1,
				"supplier": "_Test Supplier",
			},
			{
				"item_code": po_item2.item_code,
				"warehouse": "",
				"qty": 2,
				"rate": 400,
				"delivered_by_supplier": 1,
				"supplier": "_Test Supplier",
			},
		]

		# create so and po
		so = make_sales_order(item_list=so_items, do_not_submit=True)
		so.submit()

		# create po for only one item
		po1 = make_purchase_order_for_default_supplier(so.name, selected_items=[so_items[0]])[0]
		po1.submit()

		self.assertEqual(so.customer, po1.customer)
		self.assertEqual(po1.items[0].sales_order, so.name)
		self.assertEqual(po1.items[0].item_code, po_item1.item_code)
		# test po item length
		self.assertEqual(len(po1.items), 1)

		# create po for remaining item
		po2 = make_purchase_order_for_default_supplier(so.name, selected_items=[so_items[1]])[0]
		po2.submit()

		# teardown
		so_update_status("Draft", so.name)

		po1.cancel()
		po2.cancel()
		so.load_from_db()
		so.cancel()

	def test_drop_shipping_full_for_default_suppliers(self):
		"""Test if multiple POs are generated in one go against different default suppliers."""
		from erpnext.selling.doctype.sales_order.sales_order import (
			make_purchase_order_for_default_supplier,
		)

		if not frappe.db.exists("Item", "_Test Item for Drop Shipping 1"):
			make_item("_Test Item for Drop Shipping 1", {"is_stock_item": 1, "delivered_by_supplier": 1})

		if not frappe.db.exists("Item", "_Test Item for Drop Shipping 2"):
			make_item("_Test Item for Drop Shipping 2", {"is_stock_item": 1, "delivered_by_supplier": 1})

		so_items = [
			{
				"item_code": "_Test Item for Drop Shipping 1",
				"warehouse": "",
				"qty": 2,
				"rate": 400,
				"delivered_by_supplier": 1,
				"supplier": "_Test Supplier",
			},
			{
				"item_code": "_Test Item for Drop Shipping 2",
				"warehouse": "",
				"qty": 2,
				"rate": 400,
				"delivered_by_supplier": 1,
				"supplier": "_Test Supplier 1",
			},
		]

		# create so and po
		so = make_sales_order(item_list=so_items, do_not_submit=True)
		so.submit()

		purchase_orders = make_purchase_order_for_default_supplier(so.name, selected_items=so_items)

		self.assertEqual(len(purchase_orders), 2)
		self.assertEqual(purchase_orders[0].supplier, "_Test Supplier")
		self.assertEqual(purchase_orders[1].supplier, "_Test Supplier 1")

	def test_product_bundles_in_so_are_replaced_with_bundle_items_in_po(self):
		"""
		Tests if the the Product Bundles in the Items table of Sales Orders are replaced with
		their child items(from the Packed Items table) on creating a Purchase Order from it.
		"""
		from erpnext.selling.doctype.sales_order.sales_order import make_purchase_order

		product_bundle = make_item("_Test Product Bundle", {"is_stock_item": 0})
		make_item("_Test Bundle Item 1", {"is_stock_item": 1})
		make_item("_Test Bundle Item 2", {"is_stock_item": 1})

		make_product_bundle("_Test Product Bundle", ["_Test Bundle Item 1", "_Test Bundle Item 2"])

		so_items = [
			{
				"item_code": product_bundle.item_code,
				"warehouse": "",
				"qty": 2,
				"rate": 400,
				"delivered_by_supplier": 1,
				"supplier": "_Test Supplier",
			}
		]

		so = make_sales_order(item_list=so_items)

		purchase_order = make_purchase_order(so.name, selected_items=so_items)

		self.assertEqual(purchase_order.items[0].item_code, "_Test Bundle Item 1")
		self.assertEqual(purchase_order.items[1].item_code, "_Test Bundle Item 2")

	def test_purchase_order_updates_packed_item_ordered_qty(self):
		"""
		Tests if the packed item's `ordered_qty` is updated with the quantity of the Purchase Order
		"""
		from erpnext.selling.doctype.sales_order.sales_order import make_purchase_order

		product_bundle = make_item("_Test Product Bundle", {"is_stock_item": 0})
		make_item("_Test Bundle Item 1", {"is_stock_item": 1})
		make_item("_Test Bundle Item 2", {"is_stock_item": 1})

		make_product_bundle("_Test Product Bundle", ["_Test Bundle Item 1", "_Test Bundle Item 2"])

		so_items = [
			{
				"item_code": product_bundle.item_code,
				"warehouse": "",
				"qty": 2,
				"rate": 400,
				"delivered_by_supplier": 1,
				"supplier": "_Test Supplier",
			}
		]

		so = make_sales_order(item_list=so_items)

		purchase_order = make_purchase_order(so.name, selected_items=so_items)
		purchase_order.supplier = "_Test Supplier"
		purchase_order.set_warehouse = "_Test Warehouse - _TC"
		purchase_order.save()
		purchase_order.submit()

		so.reload()
		self.assertEqual(so.packed_items[0].ordered_qty, 2)
		self.assertEqual(so.packed_items[1].ordered_qty, 2)

	def test_reserved_qty_for_closing_so(self):
		bin = frappe.get_all(
			"Bin",
			filters={"item_code": "_Test Item", "warehouse": "_Test Warehouse - _TC"},
			fields=["reserved_qty"],
		)

		existing_reserved_qty = bin[0].reserved_qty if bin else 0.0

		so = make_sales_order(item_code="_Test Item", qty=1)

		self.assertEqual(
			get_reserved_qty(item_code="_Test Item", warehouse="_Test Warehouse - _TC"),
			existing_reserved_qty + 1,
		)

		so.update_status("Closed")

		self.assertEqual(
			get_reserved_qty(item_code="_Test Item", warehouse="_Test Warehouse - _TC"),
			existing_reserved_qty,
		)

	def test_create_so_with_margin(self):
		so = make_sales_order(item_code="_Test Item", qty=1, do_not_submit=True)
		so.items[0].price_list_rate = price_list_rate = 100
		so.items[0].margin_type = "Percentage"
		so.items[0].margin_rate_or_amount = 25
		so.save()

		new_so = frappe.copy_doc(so)
		new_so.save(ignore_permissions=True)

		self.assertEqual(new_so.get("items")[0].rate, flt((price_list_rate * 25) / 100 + price_list_rate))
		new_so.items[0].margin_rate_or_amount = 25
		new_so.payment_schedule = []
		new_so.save()
		new_so.submit()

		self.assertEqual(new_so.get("items")[0].rate, flt((price_list_rate * 25) / 100 + price_list_rate))

	def test_terms_auto_added(self):
		so = make_sales_order(do_not_save=1)

		self.assertFalse(so.get("payment_schedule"))

		so.insert()

		self.assertTrue(so.get("payment_schedule"))

	def test_terms_not_copied(self):
		so = make_sales_order()
		self.assertTrue(so.get("payment_schedule"))

		si = make_sales_invoice(so.name)
		self.assertFalse(si.get("payment_schedule"))

	def test_terms_copied(self):
		so = make_sales_order(do_not_copy=1, do_not_save=1)
		so.payment_terms_template = "_Test Payment Term Template"
		so.insert()
		so.submit()
		self.assertTrue(so.get("payment_schedule"))

		si = make_sales_invoice(so.name)
		si.insert()
		self.assertTrue(si.get("payment_schedule"))

	def test_make_work_order(self):
		from erpnext.selling.doctype.sales_order.sales_order import get_work_order_items

		# Make a new Sales Order
		so = make_sales_order(
			**{
				"item_list": [
					{"item_code": "_Test FG Item", "qty": 10, "rate": 100},
					{"item_code": "_Test FG Item", "qty": 20, "rate": 200},
				]
			}
		)

		# Raise Work Orders
		po_items = []
		so_item_name = {}
		for item in get_work_order_items(so.name):
			po_items.append(
				{
					"warehouse": item.get("warehouse"),
					"item_code": item.get("item_code"),
					"pending_qty": item.get("pending_qty"),
					"sales_order_item": item.get("sales_order_item"),
					"bom": item.get("bom"),
					"description": item.get("description"),
				}
			)
			so_item_name[item.get("sales_order_item")] = item.get("pending_qty")
		make_work_orders(json.dumps({"items": po_items}), so.name, so.company)

		# Check if Work Orders were raised
		for item in so_item_name:
			wo_qty = frappe.db.sql(
				"select sum(qty) from `tabWork Order` where sales_order=%s and sales_order_item=%s",
				(so.name, item),
			)
			self.assertEqual(wo_qty[0][0], so_item_name.get(item))

	def test_advance_payment_entry_unlink_against_sales_order(self):
		from erpnext.accounts.doctype.payment_entry.test_payment_entry import get_payment_entry

		frappe.db.set_single_value("Accounts Settings", "unlink_advance_payment_on_cancelation_of_order", 0)

		so = make_sales_order()

		pe = get_payment_entry("Sales Order", so.name, bank_account="_Test Bank - _TC")
		pe.reference_no = "1"
		pe.reference_date = nowdate()
		pe.paid_from_account_currency = so.currency
		pe.paid_to_account_currency = so.currency
		pe.source_exchange_rate = 1
		pe.target_exchange_rate = 1
		pe.paid_amount = so.grand_total
		pe.save(ignore_permissions=True)
		pe.submit()

		so_doc = frappe.get_doc("Sales Order", so.name)

		self.assertRaises(frappe.LinkExistsError, so_doc.cancel)

	@change_settings("Accounts Settings", {"unlink_advance_payment_on_cancelation_of_order": 1})
	def test_advance_paid_upon_payment_cancellation(self):
		from erpnext.accounts.doctype.payment_entry.test_payment_entry import get_payment_entry

		so = make_sales_order()

		pe = get_payment_entry("Sales Order", so.name, bank_account="_Test Bank - _TC")
		pe.reference_no = "1"
		pe.reference_date = nowdate()
		pe.paid_from_account_currency = so.currency
		pe.paid_to_account_currency = so.currency
		pe.source_exchange_rate = 1
		pe.target_exchange_rate = 1
		pe.paid_amount = so.grand_total
		pe.save(ignore_permissions=True)
		pe.submit()
		so.reload()

		self.assertEqual(so.advance_paid, so.base_grand_total)

		# cancel advance payment
		pe.reload()
		pe.cancel()

		so.reload()
		self.assertEqual(so.advance_paid, 0)

	def test_cancel_sales_order_after_cancel_payment_entry(self):
		from erpnext.accounts.doctype.payment_entry.test_payment_entry import get_payment_entry

		# make a sales order
		so = make_sales_order()

		# disable unlinking of payment entry
		frappe.db.set_single_value("Accounts Settings", "unlink_advance_payment_on_cancelation_of_order", 0)

		# create a payment entry against sales order
		pe = get_payment_entry("Sales Order", so.name, bank_account="_Test Bank - _TC")
		pe.reference_no = "1"
		pe.reference_date = nowdate()
		pe.paid_from_account_currency = so.currency
		pe.paid_to_account_currency = so.currency
		pe.source_exchange_rate = 1
		pe.target_exchange_rate = 1
		pe.paid_amount = so.grand_total
		pe.save(ignore_permissions=True)
		pe.submit()

		# Cancel payment entry
		po_doc = frappe.get_doc("Payment Entry", pe.name)
		po_doc.cancel()

		# Cancel sales order
		try:
			so_doc = frappe.get_doc("Sales Order", so.name)
			so_doc.cancel()
		except Exception:
			self.fail("Can not cancel sales order with linked cancelled payment entry")

	def test_work_order_pop_up_from_sales_order(self):
		"Test `get_work_order_items` in Sales Order picks the right BOM for items to manufacture."

		from erpnext.controllers.item_variant import create_variant
		from erpnext.manufacturing.doctype.production_plan.test_production_plan import make_bom
		from erpnext.selling.doctype.sales_order.sales_order import get_work_order_items

		make_item(  # template item
			"Test-WO-Tshirt",
			{
				"has_variant": 1,
				"variant_based_on": "Item Attribute",
				"attributes": [{"attribute": "Test Colour"}],
			},
		)
		make_item("Test-RM-Cotton")  # RM for BOM

		for colour in (
			"Red",
			"Green",
		):
			variant = create_variant("Test-WO-Tshirt", {"Test Colour": colour})
			variant.save()

		template_bom = make_bom(item="Test-WO-Tshirt", rate=100, raw_materials=["Test-RM-Cotton"])
		red_var_bom = make_bom(item="Test-WO-Tshirt-R", rate=100, raw_materials=["Test-RM-Cotton"])

		so = make_sales_order(
			**{
				"item_list": [
					{
						"item_code": "Test-WO-Tshirt-R",
						"qty": 1,
						"rate": 1000,
						"warehouse": "_Test Warehouse - _TC",
					},
					{
						"item_code": "Test-WO-Tshirt-G",
						"qty": 1,
						"rate": 1000,
						"warehouse": "_Test Warehouse - _TC",
					},
				]
			}
		)
		wo_items = get_work_order_items(so.name)

		self.assertEqual(wo_items[0].get("item_code"), "Test-WO-Tshirt-R")
		self.assertEqual(wo_items[0].get("bom"), red_var_bom.name)

		# Must pick Template Item BOM for Test-WO-Tshirt-G as it has no BOM
		self.assertEqual(wo_items[1].get("item_code"), "Test-WO-Tshirt-G")
		self.assertEqual(wo_items[1].get("bom"), template_bom.name)

	def test_request_for_raw_materials(self):
		from erpnext.selling.doctype.sales_order.sales_order import get_work_order_items

		item = make_item(
			"_Test Finished Item",
			{
				"is_stock_item": 1,
				"maintain_stock": 1,
				"valuation_rate": 500,
				"item_defaults": [{"default_warehouse": "_Test Warehouse - _TC", "company": "_Test Company"}],
			},
		)
		make_item(
			"_Test Raw Item A",
			{
				"maintain_stock": 1,
				"valuation_rate": 100,
				"item_defaults": [{"default_warehouse": "_Test Warehouse - _TC", "company": "_Test Company"}],
			},
		)
		make_item(
			"_Test Raw Item B",
			{
				"maintain_stock": 1,
				"valuation_rate": 200,
				"item_defaults": [{"default_warehouse": "_Test Warehouse - _TC", "company": "_Test Company"}],
			},
		)
		from erpnext.manufacturing.doctype.production_plan.test_production_plan import make_bom

		make_bom(item=item.item_code, rate=1000, raw_materials=["_Test Raw Item A", "_Test Raw Item B"])

		so = make_sales_order(**{"item_list": [{"item_code": item.item_code, "qty": 1, "rate": 1000}]})
		so.submit()
		mr_dict = frappe._dict()
		items = get_work_order_items(so.name, 1)
		mr_dict["items"] = items
		mr_dict["include_exploded_items"] = 0
		mr_dict["ignore_existing_ordered_qty"] = 1
		make_raw_material_request(mr_dict, so.company, so.name)
		mr = frappe.db.sql(
			"""select name from `tabMaterial Request` ORDER BY creation DESC LIMIT 1""", as_dict=1
		)[0]
		mr_doc = frappe.get_doc("Material Request", mr.get("name"))
		self.assertEqual(mr_doc.items[0].sales_order, so.name)

	def test_so_optional_blanket_order(self):
		"""
		Expected result: Blanket order Ordered Quantity should only be affected on Sales Order with against_blanket_order = 1.
		Second Sales Order should not add on to Blanket Orders Ordered Quantity.
		"""

		make_blanket_order(blanket_order_type="Selling", quantity=10, rate=10)

		so = make_sales_order(item_code="_Test Item", qty=5, against_blanket_order=1)
		so_doc = frappe.get_doc("Sales Order", so.get("name"))
		# To test if the SO has a Blanket Order
		self.assertTrue(so_doc.items[0].blanket_order)

		so = make_sales_order(item_code="_Test Item", qty=5, against_blanket_order=0)
		so_doc = frappe.get_doc("Sales Order", so.get("name"))
		# To test if the SO does NOT have a Blanket Order
		self.assertEqual(so_doc.items[0].blanket_order, None)

	def test_so_cancellation_when_si_drafted(self):
		"""
		Test to check if Sales Order gets cancelled if Sales Invoice is in Draft state
		Expected result: sales order should not get cancelled
		"""
		so = make_sales_order()
		so.submit()
		si = make_sales_invoice(so.name)
		si.save()

		self.assertRaises(frappe.ValidationError, so.cancel)

	def test_so_cancellation_after_si_submission(self):
		"""
		Test to check if Sales Order gets cancelled when linked Sales Invoice has been Submitted
		Expected result: Sales Order should not get cancelled
		"""
		so = make_sales_order()
		so.submit()
		si = make_sales_invoice(so.name)
		si.submit()

		so.load_from_db()
		self.assertRaises(frappe.LinkExistsError, so.cancel)

	def test_so_cancellation_after_dn_submission(self):
		"""
		Test to check if Sales Order gets cancelled when linked Delivery Note has been Submitted
		Expected result: Sales Order should not get cancelled
		"""
		so = make_sales_order()
		so.submit()
		dn = make_delivery_note(so.name)
		dn.submit()

		so.load_from_db()
		self.assertRaises(frappe.LinkExistsError, so.cancel)

	def test_so_cancellation_after_maintenance_schedule_submission(self):
		"""
		Expected result: Sales Order should not get cancelled
		"""
		so = make_sales_order()
		so.submit()
		ms = make_maintenance_schedule()
		ms.items[0].sales_order = so.name
		ms.submit()

		so.load_from_db()
		self.assertRaises(frappe.LinkExistsError, so.cancel)

	def test_so_cancellation_after_maintenance_visit_submission(self):
		"""
		Expected result: Sales Order should not get cancelled
		"""
		so = make_sales_order()
		so.submit()
		mv = make_maintenance_visit()
		mv.purposes[0].prevdoc_doctype = "Sales Order"
		mv.purposes[0].prevdoc_docname = so.name
		mv.submit()

		so.load_from_db()
		self.assertRaises(frappe.LinkExistsError, so.cancel)

	def test_so_cancellation_after_work_order_submission(self):
		"""
		Expected result: Sales Order should not get cancelled
		"""
		from erpnext.manufacturing.doctype.work_order.test_work_order import make_wo_order_test_record

		so = make_sales_order(item_code="_Test FG Item", qty=10)
		so.submit()
		make_wo_order_test_record(sales_order=so.name)

		so.load_from_db()
		self.assertRaises(frappe.LinkExistsError, so.cancel)

	def test_payment_terms_are_fetched_when_creating_sales_invoice(self):
		from erpnext.accounts.doctype.payment_entry.test_payment_entry import (
			create_payment_terms_template,
		)
		from erpnext.accounts.doctype.sales_invoice.test_sales_invoice import create_sales_invoice

		automatically_fetch_payment_terms()

		so = make_sales_order(uom="Nos", do_not_save=1)
		create_payment_terms_template()
		so.payment_terms_template = "Test Receivable Template"
		so.submit()

		si = create_sales_invoice(qty=10, do_not_save=1)
		si.items[0].sales_order = so.name
		si.items[0].so_detail = so.items[0].name
		si.insert()

		self.assertEqual(so.payment_terms_template, si.payment_terms_template)
		compare_payment_schedules(self, so, si)

		automatically_fetch_payment_terms(enable=0)

	def test_zero_amount_sales_order_billing_status(self):
		from erpnext.accounts.doctype.sales_invoice.test_sales_invoice import create_sales_invoice

		so = make_sales_order(uom="Nos", do_not_save=1)
		so.items[0].rate = 0
		so.save()
		so.submit()

		self.assertEqual(so.net_total, 0)
		self.assertEqual(so.billing_status, "Not Billed")

		si = create_sales_invoice(qty=10, do_not_save=1)
		si.price_list = "_Test Price List"
		si.items[0].rate = 0
		si.items[0].price_list_rate = 0
		si.items[0].sales_order = so.name
		si.items[0].so_detail = so.items[0].name
		si.save()
		si.submit()

		self.assertEqual(si.net_total, 0)
		so.load_from_db()
		self.assertEqual(so.billing_status, "Fully Billed")

	def test_so_billing_status_with_crnote_against_sales_return(self):
		"""
		| Step | Document creation                    |                               |
		|------+--------------------------------------+-------------------------------|
		|    1 | SO -> DN -> SI                       | SO Fully Billed and Completed |
		|    2 | DN -> Sales Return(Partial)          | SO 50% Delivered, 100% billed |
		|    3 | Sales Return(Partial) -> Credit Note | SO 50% Delivered, 50% billed  |

		"""
		from erpnext.accounts.doctype.sales_invoice.test_sales_invoice import create_sales_invoice

		so = make_sales_order(uom="Nos", do_not_save=1)
		so.save()
		so.submit()

		self.assertEqual(so.billing_status, "Not Billed")

		dn1 = make_delivery_note(so.name)
		dn1.taxes_and_charges = ""
		dn1.taxes.clear()
		dn1.save().submit()

		si = create_sales_invoice(qty=10, do_not_save=1)
		si.items[0].sales_order = so.name
		si.items[0].so_detail = so.items[0].name
		si.items[0].delivery_note = dn1.name
		si.items[0].dn_detail = dn1.items[0].name
		si.save()
		si.submit()

		so.reload()
		self.assertEqual(so.billing_status, "Fully Billed")
		self.assertEqual(so.status, "Completed")

		from erpnext.stock.doctype.delivery_note.test_delivery_note import create_delivery_note

		dn1.reload()
		dn_ret = create_delivery_note(is_return=1, return_against=dn1.name, qty=-5, do_not_submit=True)
		dn_ret.items[0].against_sales_order = so.name
		dn_ret.items[0].so_detail = so.items[0].name
		dn_ret.submit()

		so.reload()
		self.assertEqual(so.per_billed, 100)
		self.assertEqual(so.per_delivered, 50)

		cr_note = create_sales_invoice(is_return=1, qty=-1, do_not_submit=True)
		cr_note.items[0].qty = -5
		cr_note.items[0].sales_order = so.name
		cr_note.items[0].so_detail = so.items[0].name
		cr_note.items[0].delivery_note = dn_ret.name
		cr_note.items[0].dn_detail = dn_ret.items[0].name
		cr_note.update_billed_amount_in_sales_order = True
		cr_note.submit()

		so.reload()
		self.assertEqual(so.per_billed, 50)
		self.assertEqual(so.per_delivered, 50)

	def test_so_back_updated_from_wo_via_mr(self):
		"SO -> MR (Manufacture) -> WO. Test if WO Qty is updated in SO."
		from erpnext.manufacturing.doctype.work_order.work_order import (
			make_stock_entry as make_se_from_wo,
		)
		from erpnext.stock.doctype.material_request.material_request import raise_work_orders

		so = make_sales_order(item_list=[{"item_code": "_Test FG Item", "qty": 2, "rate": 100}])

		mr = make_material_request(so.name)
		mr.material_request_type = "Manufacture"
		mr.schedule_date = today()
		mr.submit()

		# WO from MR
		wo_name = raise_work_orders(mr.name)[0]
		wo = frappe.get_doc("Work Order", wo_name)
		wo.wip_warehouse = "Work In Progress - _TC"
		wo.skip_transfer = True

		self.assertEqual(wo.sales_order, so.name)
		self.assertEqual(wo.sales_order_item, so.items[0].name)

		wo.submit()
		make_stock_entry(
			item_code="_Test Item",
			target="Work In Progress - _TC",
			qty=4,
			basic_rate=100,  # Stock RM
		)
		make_stock_entry(
			item_code="_Test Item Home Desktop 100",  # Stock RM
			target="Work In Progress - _TC",
			qty=4,
			basic_rate=100,
		)

		se = frappe.get_doc(make_se_from_wo(wo.name, "Manufacture", 2))
		se.submit()  # Finish WO

		mr.reload()
		wo.reload()
		so.reload()
		self.assertEqual(so.items[0].work_order_qty, wo.produced_qty)
		self.assertEqual(mr.status, "Manufactured")

	def test_sales_order_with_shipping_rule(self):
		from erpnext.accounts.doctype.shipping_rule.test_shipping_rule import create_shipping_rule

		shipping_rule = create_shipping_rule(
			shipping_rule_type="Selling", shipping_rule_name="Shipping Rule - Sales Invoice Test"
		)
		sales_order = make_sales_order(do_not_save=True)
		sales_order.shipping_rule = shipping_rule.name

		sales_order.items[0].qty = 1
		sales_order.save()
		self.assertEqual(sales_order.taxes[0].tax_amount, 50)

		sales_order.items[0].qty = 2
		sales_order.save()
		self.assertEqual(sales_order.taxes[0].tax_amount, 100)

		sales_order.items[0].qty = 3
		sales_order.save()
		self.assertEqual(sales_order.taxes[0].tax_amount, 200)

		sales_order.items[0].qty = 21
		sales_order.save()
		self.assertEqual(sales_order.taxes[0].tax_amount, 0)

	def test_sales_order_partial_advance_payment(self):
		from erpnext.accounts.doctype.payment_entry.test_payment_entry import (
			create_payment_entry,
			get_payment_entry,
		)
		from erpnext.selling.doctype.customer.test_customer import get_customer_dict

		# Make a customer
		customer = get_customer_dict("QA Logistics")
		frappe.get_doc(customer).insert()

		# Make a Sales Order
		so = make_sales_order(
			customer="QA Logistics",
			item_list=[
				{"item_code": "_Test Item", "qty": 1, "rate": 200},
				{"item_code": "_Test Item 2", "qty": 1, "rate": 300},
			],
		)

		# Create a advance payment against that Sales Order
		pe = get_payment_entry("Sales Order", so.name, bank_account="_Test Bank - _TC")
		pe.reference_no = "1"
		pe.reference_date = nowdate()
		pe.paid_from_account_currency = so.currency
		pe.paid_to_account_currency = so.currency
		pe.source_exchange_rate = 1
		pe.target_exchange_rate = 1
		pe.paid_amount = so.grand_total
		pe.save(ignore_permissions=True)
		pe.submit()

		# Make standalone advance payment entry
		create_payment_entry(
			payment_type="Receive",
			party_type="Customer",
			party="QA Logistics",
			paid_from="Debtors - _TC",
			paid_to="_Test Bank - _TC",
			save=1,
			submit=1,
		)

		si = make_sales_invoice(so.name)

		item = si.get("items")[1]
		si.remove(item)

		si.allocate_advances_automatically = 1
		si.save()

		self.assertEqual(len(si.get("advances")), 1)
		self.assertEqual(si.get("advances")[0].allocated_amount, 200)
		self.assertEqual(si.get("advances")[0].reference_name, pe.name)

		si.submit()
		pe.load_from_db()

		self.assertEqual(pe.references[0].reference_name, so.name)
		self.assertEqual(pe.references[0].allocated_amount, 300)
		self.assertEqual(pe.references[1].reference_name, si.name)
		self.assertEqual(pe.references[1].allocated_amount, 200)

	def test_delivered_item_material_request(self):
		"SO -> MR (Manufacture) -> WO. Test if WO Qty is updated in SO."

		so = make_sales_order(
			item_list=[
				{"item_code": "_Test FG Item", "qty": 10, "rate": 100, "warehouse": "Work In Progress - _TC"}
			]
		)

		make_stock_entry(item_code="_Test FG Item", target="Work In Progress - _TC", qty=4, basic_rate=100)

		dn = make_delivery_note(so.name)
		dn.items[0].qty = 4
		dn.submit()

		so.load_from_db()
		self.assertEqual(so.items[0].delivered_qty, 4)

		mr = make_material_request(so.name)
		mr.material_request_type = "Purchase"
		mr.schedule_date = today()
		mr.save()

		self.assertEqual(mr.items[0].qty, 6)

	def test_packed_items_for_partial_sales_order(self):
		# test Update Items with product bundle
		for product_bundle in [
			"_Test Product Bundle Item Partial 1",
			"_Test Product Bundle Item Partial 2",
		]:
			if not frappe.db.exists("Item", product_bundle):
				bundle_item = make_item(product_bundle, {"is_stock_item": 0})
				bundle_item.append(
					"item_defaults",
					{"company": "_Test Company", "default_warehouse": "_Test Warehouse - _TC"},
				)
				bundle_item.save(ignore_permissions=True)

		for product_bundle in ["_Packed Item Partial 1", "_Packed Item Partial 2"]:
			if not frappe.db.exists("Item", product_bundle):
				make_item(product_bundle, {"is_stock_item": 1, "stock_uom": "Nos"})

			make_stock_entry(item=product_bundle, target="_Test Warehouse - _TC", qty=2, rate=10)

		make_product_bundle("_Test Product Bundle Item Partial 1", ["_Packed Item Partial 1"], 1)

		make_product_bundle("_Test Product Bundle Item Partial 2", ["_Packed Item Partial 2"], 1)

		so = make_sales_order(
			item_code="_Test Product Bundle Item Partial 1",
			warehouse="_Test Warehouse - _TC",
			qty=1,
			uom="Nos",
			stock_uom="Nos",
			conversion_factor=1,
			transaction_date=nowdate(),
			delivery_note=nowdate(),
			do_not_submit=1,
		)

		so.append(
			"items",
			{
				"item_code": "_Test Product Bundle Item Partial 2",
				"warehouse": "_Test Warehouse - _TC",
				"qty": 1,
				"uom": "Nos",
				"stock_uom": "Nos",
				"conversion_factor": 1,
				"delivery_note": nowdate(),
			},
		)

		so.save()
		so.submit()

		dn = make_delivery_note(so.name)
		dn.remove(dn.items[1])
		dn.save()
		dn.submit()

		self.assertEqual(len(dn.items), 1)
		self.assertEqual(len(dn.packed_items), 1)
		self.assertEqual(dn.items[0].item_code, "_Test Product Bundle Item Partial 1")

		so.load_from_db()

		dn = make_delivery_note(so.name)
		dn.save()

		self.assertEqual(len(dn.items), 1)
		self.assertEqual(len(dn.packed_items), 1)
		self.assertEqual(dn.items[0].item_code, "_Test Product Bundle Item Partial 2")

	@change_settings("Selling Settings", {"editable_bundle_item_rates": 1})
	def test_expired_rate_for_packed_item(self):
		bundle = "_Test Product Bundle 1"
		packed_item = "_Packed Item 1"

		# test Update Items with product bundle
		for product_bundle in [bundle]:
			if not frappe.db.exists("Item", product_bundle):
				bundle_item = make_item(product_bundle, {"is_stock_item": 0})
				bundle_item.append(
					"item_defaults",
					{"company": "_Test Company", "default_warehouse": "_Test Warehouse - _TC"},
				)
				bundle_item.save(ignore_permissions=True)

		for product_bundle in [packed_item]:
			if not frappe.db.exists("Item", product_bundle):
				make_item(product_bundle, {"is_stock_item": 0, "stock_uom": "Nos"})

		make_product_bundle(bundle, [packed_item], 1)

		for scenario in [
			{"valid_upto": add_days(nowdate(), -1), "expected_rate": 0.0},
			{"valid_upto": add_days(nowdate(), 1), "expected_rate": 111.0},
		]:
			with self.subTest(scenario=scenario):
				frappe.get_doc(
					{
						"doctype": "Item Price",
						"item_code": packed_item,
						"selling": 1,
						"price_list": "_Test Price List",
						"valid_from": add_days(nowdate(), -1),
						"valid_upto": scenario.get("valid_upto"),
						"price_list_rate": 111,
					}
				).save()

				so = frappe.new_doc("Sales Order")
				so.transaction_date = nowdate()
				so.delivery_date = nowdate()
				so.set_warehouse = ""
				so.company = "_Test Company"
				so.customer = "_Test Customer"
				so.currency = "INR"
				so.selling_price_list = "_Test Price List"
				so.append("items", {"item_code": bundle, "qty": 1})
				so.save()

				self.assertEqual(len(so.items), 1)
				self.assertEqual(len(so.packed_items), 1)
				self.assertEqual(so.items[0].item_code, bundle)
				self.assertEqual(so.packed_items[0].item_code, packed_item)
				self.assertEqual(so.items[0].rate, scenario.get("expected_rate"))
				self.assertEqual(so.packed_items[0].rate, scenario.get("expected_rate"))

	def test_pick_list_without_rejected_materials(self):
		serial_and_batch_item = make_item(
			"_Test Serial and Batch Item for Rejected Materials",
			properties={
				"has_serial_no": 1,
				"has_batch_no": 1,
				"create_new_batch": 1,
				"batch_number_series": "BAT-TSBIFRM-.#####",
				"serial_no_series": "SN-TSBIFRM-.#####",
			},
		).name

		serial_item = make_item(
			"_Test Serial Item for Rejected Materials",
			properties={
				"has_serial_no": 1,
				"serial_no_series": "SN-TSIFRM-.#####",
			},
		).name

		batch_item = make_item(
			"_Test Batch Item for Rejected Materials",
			properties={
				"has_batch_no": 1,
				"create_new_batch": 1,
				"batch_number_series": "BAT-TBIFRM-.#####",
			},
		).name

		normal_item = make_item("_Test Normal Item for Rejected Materials").name

		warehouse = "_Test Warehouse - _TC"
		rejected_warehouse = "_Test Dummy Rejected Warehouse - _TC"

		if not frappe.db.exists("Warehouse", rejected_warehouse):
			frappe.get_doc(
				{
					"doctype": "Warehouse",
					"warehouse_name": rejected_warehouse,
					"company": "_Test Company",
					"warehouse_group": "_Test Warehouse Group",
					"is_rejected_warehouse": 1,
				}
			).insert()

		se = make_stock_entry(item_code=normal_item, qty=1, to_warehouse=warehouse, do_not_submit=True)
		for item in [serial_and_batch_item, serial_item, batch_item]:
			se.append("items", {"item_code": item, "qty": 1, "t_warehouse": warehouse})

		se.save()
		se.submit()

		se = make_stock_entry(
			item_code=normal_item, qty=1, to_warehouse=rejected_warehouse, do_not_submit=True
		)
		for item in [serial_and_batch_item, serial_item, batch_item]:
			se.append("items", {"item_code": item, "qty": 1, "t_warehouse": rejected_warehouse})

		se.save()
		se.submit()

		so = make_sales_order(item_code=normal_item, qty=2, do_not_submit=True)

		for item in [serial_and_batch_item, serial_item, batch_item]:
			so.append("items", {"item_code": item, "qty": 2, "warehouse": warehouse})

		so.save()
		so.submit()

		pick_list = create_pick_list(so.name)

		pick_list.save()
		for row in pick_list.locations:
			self.assertEqual(row.qty, 1.0)
			self.assertFalse(row.warehouse == rejected_warehouse)
			self.assertTrue(row.warehouse == warehouse)

	def test_pick_list_for_batch(self):
		from erpnext.stock.doctype.pick_list.pick_list import create_delivery_note

		batch_item = make_item(
			"_Test Batch Item for Pick LIST",
			properties={
				"has_batch_no": 1,
				"create_new_batch": 1,
				"batch_number_series": "BATCH-SDDTBIFRM-.#####",
			},
		).name

		warehouse = "_Test Warehouse - _TC"
		se = make_stock_entry(item_code=batch_item, qty=10, target=warehouse, use_serial_batch_fields=1)
		so = make_sales_order(item_code=batch_item, qty=10, warehouse=warehouse)
		pick_list = create_pick_list(so.name)

		pick_list.save()
		batch_no = frappe.get_all(
			"Serial and Batch Entry",
			filters={"parent": se.items[0].serial_and_batch_bundle},
			fields=["batch_no"],
		)[0].batch_no

		for row in pick_list.locations:
			self.assertEqual(row.qty, 10.0)
			self.assertTrue(row.warehouse == warehouse)
			self.assertTrue(row.batch_no == batch_no)

		pick_list.submit()

		dn = create_delivery_note(pick_list.name)
		for row in dn.items:
			self.assertEqual(row.qty, 10.0)
			self.assertTrue(row.warehouse == warehouse)
			self.assertTrue(row.batch_no == batch_no)

		dn.submit()
		dn.reload()

	def test_auto_update_price_list(self):
		item = make_item(
			"_Test Auto Update Price List Item",
		)

		frappe.db.set_single_value("Stock Settings", "auto_insert_price_list_rate_if_missing", 1)
		so = make_sales_order(
			item_code=item.name, currency="USD", qty=1, rate=100, price_list_rate=100, do_not_submit=True
		)
		so.save()

		item_price = frappe.db.get_value("Item Price", {"item_code": item.name}, "price_list_rate")
		self.assertEqual(item_price, 100)

		so = make_sales_order(
			item_code=item.name, currency="USD", qty=1, rate=200, price_list_rate=100, do_not_submit=True
		)
		so.save()

		item_price = frappe.db.get_value("Item Price", {"item_code": item.name}, "price_list_rate")
		self.assertEqual(item_price, 100)

		frappe.db.set_single_value("Stock Settings", "update_existing_price_list_rate", 1)
		so = make_sales_order(
			item_code=item.name, currency="USD", qty=1, rate=200, price_list_rate=200, do_not_submit=True
		)
		so.save()

		item_price = frappe.db.get_value("Item Price", {"item_code": item.name}, "price_list_rate")
		self.assertEqual(item_price, 200)

		frappe.db.set_single_value("Stock Settings", "update_existing_price_list_rate", 0)
		frappe.db.set_single_value("Stock Settings", "auto_insert_price_list_rate_if_missing", 0)

	def test_credit_limit_on_so_reopning(self):
		# set credit limit
		company = "_Test Company"
		customer = frappe.get_doc("Customer", self.customer)
		# dynamic credit limit
		credit_amt = frappe.db.sql(
						"""
						SELECT SUM(grand_total) AS total
						FROM `tabSales Order`
						WHERE customer = %s AND company = %s AND docstatus = 1
						""",(customer.name, company),as_dict=True)
		so_amt = frappe.db.get_value("Sales Order", {"customer": self.customer, "company": company}, "grand_total")
		customer_credit_amt = credit_amt[0].get("total") + so_amt
		
		customer.credit_limits = []
		customer.append(
			"credit_limits", {"company": company, "credit_limit": customer_credit_amt, "bypass_credit_limit_check": False}
		)
		customer.save()

		so1 = make_sales_order(qty=9, rate=100, do_not_submit=True)
		so1.customer = self.customer
		so1.save().submit()

		so1.update_status("Closed")

		so2 = make_sales_order(qty=9, rate=100, do_not_submit=True)
		so2.customer = self.customer
		so2.save().submit()

		self.assertRaises(frappe.ValidationError, so1.update_status, "Draft")
	
	def test_sales_order_discount_on_total(self):
		make_item_price()
		make_pricing_rule()
		so = make_sales_order(qty=10, rate=100, do_not_save=True)
		so.save()
		so.submit()
		self.assertEqual(so.total,900)
	
	def test_manual_discount_for_sales_order(self):
		so = make_sales_order(qty=10, rate=100, do_not_save=True)
		so.save()
		self.assertEqual(so.grand_total,1000)
		so.apply_discount_on = 'Grand Total'
		so.additional_discount_percentage = 10
		so.save()
		self.assertEqual(so.grand_total,900)
	
	def test_line_item_discount(self):
		make_item_price()
		so = make_sales_order(qty=1, rate=90, do_not_save=True)
		so.save()
		self.assertEqual(so.items[0].discount_amount,10)
		so.items[0].rate = 110
		so.save()
		self.assertEqual(so.items[0].margin_rate_or_amount,10)	
  
	def test_sales_order_with_advance_payment_TC_S_040(self):
		so = make_sales_order(qty=1, rate=3000, do_not_save=True)
		so.save()
		so.submit()

		self.assertEqual(so.status, 'To Deliver and Bill')

		# create payment entry
		from erpnext.accounts.doctype.payment_entry.test_payment_entry import (get_payment_entry)

		pe = get_payment_entry("Sales Order", so.name)
		pe.reference_no = "1"
		pe.reference_date = nowdate()
		pe.paid_from_account_currency = so.currency
		pe.paid_to_account_currency = so.currency
		pe.source_exchange_rate = 1
		pe.target_exchange_rate = 1
		pe.paid_amount = so.grand_total
		pe.save(ignore_permissions=True)
		pe.submit()

		self.assertEqual(pe.status, 'Submitted')

        # check if the advance payment is recorded in the Sales Order
		so.reload()
		self.assertEqual(so.advance_paid, 3000)

		#create delivery note
		dn = make_delivery_note(so.name)
		dn.submit()

		# assert that 1 quantity is deducted from the warehouse stock
		ordered_qty = frappe.db.get_value('Bin', {'item_code': '_Test Item', 'warehouse': '_Test Warehouse - _TC'}, 'ordered_qty')
		self.assertEqual(ordered_qty, 1)

		# check if the stock ledger and general ledger are updated
		stock_ledger = frappe.get_all('Stock Ledger Entry', filters={'voucher_type': 'Delivery Note', 'voucher_no': dn.name, 'warehouse': '_Test Warehouse - _TC'})
		self.assertGreater(len(stock_ledger), 0)

		from erpnext.stock.doctype.delivery_note.delivery_note import (make_sales_invoice)

		si = make_sales_invoice(dn.name)
		si.submit()

		self.assertEqual(si.status, 'Paid')
		self.assertEqual(si.outstanding_amount, 0)
		self.assertEqual(si.total_advance, 3000)

		gl_entries = frappe.get_all('GL Entry', filters={'voucher_type': 'Sales Invoice', 'voucher_no': si.name})
		self.assertGreater(len(gl_entries), 0)
  
	def test_sales_order_full_qty_process_TC_S_001(self):
		so = make_sales_order(cost_center='Main - _TC', selling_price_list='Standard Selling', qty=5, rate=5000, do_not_save=True)
		so.save()
		so.submit()
  
		self.assertEqual(so.status, "To Deliver and Bill", "Sales Order not created")
  
		dn = make_delivery_note(so.name)
		dn.save()
		dn.submit()
  
		self.assertEqual(dn.status, "To Bill", "Delivery Note not created")
  
		qty_change = frappe.db.get_value('Stock Ledger Entry', {'item_code': '_Test Item', 'voucher_no': dn.name, 'warehouse': '_Test Warehouse - _TC'}, 'actual_qty')
		self.assertEqual(qty_change, -5)
  
		from erpnext.stock.doctype.delivery_note.delivery_note import (make_sales_invoice)
  
		si = make_sales_invoice(dn.name)
		si.save()
		si.submit()
    
		si_acc_credit = frappe.db.get_value('GL Entry', {'voucher_type': 'Sales Invoice', 'voucher_no': si.name, 'account': 'Sales - _TC'}, 'credit')
		self.assertEqual(si_acc_credit, 25000)

		si_acc_debit = frappe.db.get_value('GL Entry', {'voucher_type': 'Sales Invoice', 'voucher_no': si.name, 'account': 'Debtors - _TC'}, 'debit')
		self.assertEqual(si_acc_debit, 25000)
    
  
	def test_sales_order_with_partial_advance_payment_TC_S_041(self):
		so = make_sales_order(cost_center='Main - _TC', selling_price_list='Standard Selling', qty=1, rate=5000, do_not_save=True)
		so.save()
		so.submit()

		self.assertEqual(so.status, "To Deliver and Bill", "Sales Order not created")

		from erpnext.accounts.doctype.payment_entry.test_payment_entry import (get_payment_entry)
		pe = get_payment_entry("Sales Order", so.name)
		pe.reference_no = "1"
		pe.reference_date = nowdate()
		pe.paid_from_account_currency = so.currency
		pe.paid_to_account_currency = so.currency
		pe.source_exchange_rate = 1
		pe.target_exchange_rate = 1
		pe.paid_amount = 2000
		pe.difference_amount = 0
		pe.save(ignore_permissions=True)
		pe.submit()

		self.assertEqual(pe.status, 'Submitted', 'Payment Entry not submitted')	

		so.reload()
		self.assertEqual(so.advance_paid, 2000)

		pe_acc_credit = frappe.db.get_value('GL Entry', {'voucher_type': 'Payment Entry', 'voucher_no': pe.name, 'account': 'Debtors - _TC'}, 'credit')
		self.assertEqual(pe_acc_credit, 2000)

		pe_acc_debit = frappe.db.get_value('GL Entry', {'voucher_type': 'Payment Entry', 'voucher_no': pe.name, 'account': 'Cash - _TC'}, 'debit')
		self.assertEqual(pe_acc_debit, 2000)

		dn = make_delivery_note(so.name)
		dn.submit()

		# check if the stock ledger and general ledger are updated
		qty_change = frappe.db.get_value('Stock Ledger Entry', {'voucher_type': 'Delivery Note', 'voucher_no': dn.name, 'warehouse': '_Test Warehouse - _TC', 'item_code': '_Test Item'}, 'actual_qty')
		self.assertEqual(qty_change, -1)

		from erpnext.stock.doctype.delivery_note.delivery_note import (make_sales_invoice)

		si = make_sales_invoice(dn.name)
		si.allocate_advances_automatically = 1
		si.save()
		si.submit()

		self.assertEqual(si.status, 'Partly Paid')
		self.assertEqual(si.outstanding_amount, 3000)
		self.assertEqual(si.total_advance, 2000)

		si_acc_credit = frappe.db.get_value('GL Entry', {'voucher_type': 'Sales Invoice', 'voucher_no': si.name, 'account': 'Sales - _TC'}, 'credit')
		self.assertEqual(si_acc_credit, 5000)

		si_acc_debit = frappe.db.get_value('GL Entry', {'voucher_type': 'Sales Invoice', 'voucher_no': si.name, 'account': 'Debtors - _TC'}, 'debit')
		self.assertEqual(si_acc_debit, 5000)

		# creating payment entry for remaining payment
		pe2 = get_payment_entry("Sales Order", so.name)
		pe.reference_no = "1"
		pe.reference_date = nowdate()
		pe2.paid_from_account_currency = so.currency
		pe2.paid_to_account_currency = so.currency
		pe.source_exchange_rate = 1
		pe.target_exchange_rate = 1
		pe2.save(ignore_permissions=True)
		pe2.submit()

		pe2_acc_credit = frappe.db.get_value('GL Entry', {'voucher_type': 'Payment Entry', 'voucher_no': pe2.name, 'account': 'Debtors - _TC'}, 'credit')
		self.assertEqual(pe2_acc_credit, 3000)

		pe2_acc_debit = frappe.db.get_value('GL Entry', {'voucher_type': 'Payment Entry', 'voucher_no': pe2.name, 'account': 'Cash - _TC'}, 'debit')
		self.assertEqual(pe2_acc_debit, 3000)

		# check updated sales invoice
		si.reload()
		self.assertEqual(si.status, 'Paid')
		self.assertEqual(si.outstanding_amount, 0)
  
	def test_sales_order_for_partial_delivery_TC_S_002(self):
		so = make_sales_order(cost_center='Main - _TC', selling_price_list='Standard Selling', qty=5, rate=5000, do_not_save=True)
		so.save()
		so.submit()

		self.assertEqual(so.status, "To Deliver and Bill", "Sales Order not created")

		dn = make_delivery_note(so.name)
		dn.items[0].qty = 3
		dn.save()
		dn.submit()

		self.assertEqual(dn.status, "To Bill", "Delivery Note not created")

		qty_change = frappe.db.get_value('Stock Ledger Entry', {'item_code': '_Test Item', 'voucher_no': dn.name, 'warehouse': '_Test Warehouse - _TC'}, 'actual_qty')
		self.assertEqual(qty_change, -3)

		from erpnext.stock.doctype.delivery_note.delivery_note import (make_sales_invoice)

		si = make_sales_invoice(dn.name)
		si.save()
		si.submit()

		self.assertEqual(si.status, "Unpaid", "Sales Invoice not created")

		si_acc_credit = frappe.db.get_value('GL Entry', {'voucher_type': 'Sales Invoice', 'voucher_no': si.name, 'account': 'Sales - _TC'}, 'credit')
		self.assertEqual(si_acc_credit, 15000)

		si_acc_debit = frappe.db.get_value('GL Entry', {'voucher_type': 'Sales Invoice', 'voucher_no': si.name, 'account': 'Debtors - _TC'}, 'debit')
		self.assertEqual(si_acc_debit, 15000)

		dn2 = make_delivery_note(so.name)
		dn2.save()
		dn2.submit()	

		self.assertEqual(dn2.status, "To Bill", "Delivery Note not created")

		qty_change2 = frappe.db.get_value('Stock Ledger Entry', {'item_code': '_Test Item', 'voucher_no': dn2.name, 'warehouse': '_Test Warehouse - _TC'}, 'actual_qty')
		self.assertEqual(qty_change2, -2)

		si2 = make_sales_invoice(dn2.name)
		si2.save()
		si2.submit()

		si_acc_credit2 = frappe.db.get_value('GL Entry', {'voucher_type': 'Sales Invoice', 'voucher_no': si2.name, 'account': 'Sales - _TC'}, 'credit')
		self.assertEqual(si_acc_credit2, 10000)

		si_acc_debit2 = frappe.db.get_value('GL Entry', {'voucher_type': 'Sales Invoice', 'voucher_no': si2.name, 'account': 'Debtors - _TC'}, 'debit')
		self.assertEqual(si_acc_debit2, 10000)

		self.assertEqual(si2.status, "Unpaid", "Sales Invoice not created")
  
	def test_sales_order_with_partial_sales_invoice_TC_S_003(self):
		so = make_sales_order(cost_center='Main - _TC', selling_price_list='Standard Selling', qty=4, rate=5000, do_not_save=True)
		so.save()
		so.submit()

		self.assertEqual(so.status, "To Deliver and Bill", "Sales Order not created")

		dn = make_delivery_note(so.name)
		dn.save()
		dn.submit()

		self.assertEqual(dn.status, "To Bill", "Delivery Note not created")

		qty_change = frappe.get_all('Stock Ledger Entry', {'item_code': '_Test Item', 'voucher_no': dn.name, 'warehouse': '_Test Warehouse - _TC'}, ['actual_qty', 'valuation_rate'])
		self.assertEqual(qty_change, -4)

		from erpnext.stock.doctype.delivery_note.delivery_note import (make_sales_invoice)

		si1 = make_sales_invoice(dn.name)
		si1.get("items")[0].qty = 2
		si1.insert()
		si1.submit()

		self.assertEqual(si1.status, "Unpaid", "Sales Invoice not created")

		si1_acc_credit = frappe.db.get_value('GL Entry', {'voucher_type': 'Sales Invoice', 'voucher_no': si1.name, 'account': 'Sales - _TC'}, 'credit')
		self.assertEqual(si1_acc_credit, 10000)

		si1_acc_debit = frappe.db.get_value('GL Entry', {'voucher_type': 'Sales Invoice', 'voucher_no': si1.name, 'account': 'Debtors - _TC'}, 'debit')
		self.assertEqual(si1_acc_debit, 10000)

		si2 = make_sales_invoice(dn.name)
		si2.insert()
		si2.submit()

		self.assertEqual(si2.status, "Unpaid", "Sales Invoice not created")

		si2_acc_credit = frappe.db.get_value('GL Entry', {'voucher_type': 'Sales Invoice', 'voucher_no': si2.name, 'account': 'Sales - _TC'}, 'credit')
		self.assertEqual(si2_acc_credit, 10000)

		si2_acc_debit = frappe.db.get_value('GL Entry', {'voucher_type': 'Sales Invoice', 'voucher_no': si2.name, 'account': 'Debtors - _TC'}, 'debit')
		self.assertEqual(si2_acc_debit, 10000)
  
	def test_sales_order_via_sales_invoice_TC_S_004(self):
		so = make_sales_order(cost_center='Main - _TC', selling_price_list='Standard Selling', qty=4, rate=5000, do_not_save=True)
		so.save()
		so.submit()

		self.assertEqual(so.status, "To Deliver and Bill", "Sales Order not created")

		si = make_sales_invoice(so.name)
		si.save()
		si.submit()

		self.assertEqual(si.status, "Unpaid", "Sales Invoice not created")

		si_acc_credit = frappe.db.get_value('GL Entry', {'voucher_type': 'Sales Invoice', 'voucher_no': si.name, 'account': 'Sales - _TC'}, 'credit')
		self.assertEqual(si_acc_credit, 20000)

		si_acc_debit = frappe.db.get_value('GL Entry', {'voucher_type': 'Sales Invoice', 'voucher_no': si.name, 'account': 'Debtors - _TC'}, 'debit')
		self.assertEqual(si_acc_debit, 20000)

		from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_delivery_note
		dn = make_delivery_note(si.name)
		dn.save()
		dn.submit()

		self.assertEqual(dn.status, "Completed", "Delivery Note not created")

		qty_change = frappe.db.get_value('Stock Ledger Entry', {'item_code': '_Test Item', 'voucher_no': dn.name, 'warehouse': '_Test Warehouse - _TC'}, 'actual_qty')
		self.assertEqual(qty_change, -4)
  
	def test_sales_order_with_update_stock_in_si_TC_S_008(self):
		so = make_sales_order(cost_center='Main - _TC', selling_price_list='Standard Selling', qty=4, rate=5000, do_not_save=True)
		so.save()
		so.submit()

		self.assertEqual(so.status, "To Deliver and Bill", "Sales Order not created")

		si = make_sales_invoice(so.name)
		si.update_stock = 1
		si.save()
		si.submit()

		self.assertEqual(si.status, "Unpaid", "Sales Invoice not created")

		voucher_params = {
			'voucher_type': 'Sales Invoice','voucher_no': si.name
		}
		gl_accounts = {
			'Sales - _TC': 'credit','Debtors - _TC': 'debit'
		}

		gl_entries = {
			account: frappe.db.get_value('GL Entry', {**voucher_params, 'account': account}, field)
			for account, field in gl_accounts.items()
		}

		qty_change = frappe.db.get_value('Stock Ledger Entry', {**voucher_params, 'item_code': '_Test Item', 'warehouse': '_Test Warehouse - _TC'}, 'actual_qty')

		self.assertEqual(qty_change, -4)
		self.assertEqual(gl_entries['Sales - _TC'], 20000)
		self.assertEqual(gl_entries['Debtors - _TC'], 20000)

		so.reload()
		self.assertEqual(so.status, 'Completed')
  
	def test_sales_order_for_partial_dn_via_si_TC_S_005(self):
		so = make_sales_order(cost_center='Main - _TC', selling_price_list='Standard Selling', qty=4, rate=5000, do_not_save=True)
		so.save()
		so.submit()

		self.assertEqual(so.status, "To Deliver and Bill", "Sales Order not created")

		si = make_sales_invoice(so.name)
		si.save()
		si.submit()

		self.assertEqual(si.status, "Unpaid", "Sales Invoice not created")

		si_acc_credit = frappe.db.get_value('GL Entry', {'voucher_type': 'Sales Invoice', 'voucher_no': si.name, 'account': 'Sales - _TC'}, 'credit')
		self.assertEqual(si_acc_credit, 20000)

		si_acc_debit = frappe.db.get_value('GL Entry', {'voucher_type': 'Sales Invoice', 'voucher_no': si.name, 'account': 'Debtors - _TC'}, 'debit')
		self.assertEqual(si_acc_debit, 20000)

		from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_delivery_note
		dn1 = make_delivery_note(si.name)
		dn1.get("items")[0].qty = 2
		dn1.save()
		dn1.submit()

		self.assertEqual(dn1.status, "Completed", "Delivery Note not created")

		qty_change1 = frappe.db.get_value('Stock Ledger Entry', {'item_code': '_Test Item', 'voucher_no': dn1.name, 'warehouse': '_Test Warehouse - _TC'}, 'actual_qty')
		self.assertEqual(qty_change1, -2)

		dn2 = make_delivery_note(si.name)
		dn2.save()
		dn2.submit()

		self.assertEqual(dn2.status, "Completed", "Delivery Note not created")

		qty_change2 = frappe.db.get_value('Stock Ledger Entry', {'item_code': '_Test Item', 'voucher_no': dn2.name, 'warehouse': '_Test Warehouse - _TC'}, 'actual_qty')
		self.assertEqual(qty_change2, -2)
  
	def test_sales_order_with_update_stock_in_partial_si_TC_S_009(self):
		so = make_sales_order(cost_center='Main - _TC', selling_price_list='Standard Selling', qty=4, rate=5000, do_not_save=True)
		so.save()
		so.submit()

		self.assertEqual(so.status, "To Deliver and Bill", "Sales Order not created")

		si1 = make_sales_invoice(so.name)
		si1.get("items")[0].qty = 2
		si1.update_stock = 1
		si1.save()
		si1.submit()

		self.assertEqual(si1.status, "Unpaid", "Sales Invoice not created")
  
		voucher_params = {
			'voucher_type': 'Sales Invoice','voucher_no': si1.name
		}

		gl_accounts = {
			'Sales - _TC': 'credit','Debtors - _TC': 'debit'
		}

		gl_entries = {
			account: frappe.db.get_value('GL Entry', {**voucher_params, 'account': account}, field)
			for account, field in gl_accounts.items()
		}

		qty_change1 = frappe.db.get_value('Stock Ledger Entry', {**voucher_params, 'item_code': '_Test Item', 'warehouse': '_Test Warehouse - _TC'}, 'actual_qty')

		self.assertEqual(qty_change1, -2)
		self.assertEqual(gl_entries['Sales - _TC'], 10000)
		self.assertEqual(gl_entries['Debtors - _TC'], 10000)
  
		si2 = make_sales_invoice(so.name)
		si2.update_stock = 1
		si2.save()
		si2.submit()

		self.assertEqual(si2.status, "Unpaid", "Sales Invoice not created")

		voucher_params_si2 = {
			'voucher_type': 'Sales Invoice','voucher_no': si2.name
		}

		gl_accounts = {
			'Sales - _TC': 'credit','Debtors - _TC': 'debit'
		}

		gl_entries_si2 = {
			account: frappe.db.get_value('GL Entry', {**voucher_params_si2, 'account': account}, field)
			for account, field in gl_accounts.items()
		}

		qty_change2 = frappe.db.get_value('Stock Ledger Entry', {**voucher_params_si2, 'item_code': '_Test Item', 'warehouse': '_Test Warehouse - _TC'}, 'actual_qty')

		self.assertEqual(qty_change2, -2)
		self.assertEqual(gl_entries_si2['Sales - _TC'], 10000)
		self.assertEqual(gl_entries_si2['Debtors - _TC'], 10000)


		so.reload()
		self.assertEqual(so.status, 'Completed')
  
	def test_sales_order_for_service_item_TC_S_010(self):
		make_service_item()
  
		so = make_sales_order(cost_center='Main - _TC', selling_price_list='Standard Selling', item_code='Consultancy', qty=1, rate=5000)
		so.save()
		so.submit()

		self.assertEqual(so.status, "To Deliver and Bill", "Sales Order not created")
  
		si = make_sales_invoice(so.name)
		si.save()
		si.submit()

		self.assertEqual(si.status, "Unpaid", "Sales Invoice not created")
  
		si_acc_credit = frappe.db.get_value('GL Entry', {'voucher_type': 'Sales Invoice', 'voucher_no': si.name, 'account': 'Sales - FC'}, 'credit')
		self.assertEqual(si_acc_credit, 5000)

		si_acc_debit = frappe.db.get_value('GL Entry', {'voucher_type': 'Sales Invoice', 'voucher_no': si.name, 'account': 'Debtors - FC'}, 'debit')
		self.assertEqual(si_acc_debit, 5000)
  
	def test_sales_order_full_payment_with_gst_TC_S_011(self):
		company = frappe.get_all("Company", {"name": "_Test Indian Registered Company"}, ["gstin", "gst_category"])
		customer = frappe.get_all("Customer", {"name": "_Test Registered Customer"}, ["gstin", "gst_category"])
		company_add = frappe.get_all("Address", {"name": "_Test Indian Registered Company-Billing"}, ["name", "gstin", "gst_category"])
		customer_add = frappe.get_all("Address", {"name": "_Test Registered Customer-Billing"}, ["name", "gstin", "gst_category"])
  
		if company[0].get("gst_category") == "Registered Regular" and customer[0].get("gst_category") == "Registered Regular" and customer[0].get("gstin") and customer[0].get("gstin"):
			if company_add[0].get("gst_category") == "Registered Regular" and customer_add[0].get("gst_category") == "Registered Regular" and company_add[0].get("gstin") and customer_add[0].get("gstin"):
				so = make_sales_order(company='_Test Indian Registered Company', customer='_Test Registered Customer', warehouse='Stores - _TIRC' ,cost_center='Main - _TIRC', selling_price_list='Standard Selling', item_code='_Test Item', qty=1, rate=5000, do_not_save=True)
				so.tax_category = 'In-State'
				so.taxes_and_charges = 'Output GST In-state - _TIRC'
				so.customer_address = customer_add[0].get("name")
				so.billing_address_gstin = customer_add[0].get("gstin")
				so.company_address = company_add[0].get("name")
				so.company_gstin = company_add[0].get("gstin")
				so.save()
				so.submit()

				self.assertEqual(so.status, "To Deliver and Bill", "Sales Order not created")
				self.assertEqual(so.grand_total, so.total + so.total_taxes_and_charges)

				dn = make_delivery_note(so.name)
				dn.save()
				dn.submit()

				self.assertEqual(dn.status, "To Bill", "Delivery Note not created")

				qty_change = frappe.get_all('Stock Ledger Entry', {'item_code': '_Test Item', 'voucher_no': dn.name, 'warehouse': 'Stores - _TIRC'}, ['actual_qty', 'valuation_rate'])
				self.assertEqual(qty_change[0].get("actual_qty"), -1)
    
				dn_acc_credit1 = frappe.db.get_value('GL Entry', {'voucher_type': 'Delivery Note', 'voucher_no': dn.name, 'account': 'Stock In Hand - _TIRC'}, 'credit')
				self.assertEqual(dn_acc_credit1, qty_change[0].get("valuation_rate") * 1)

				dn_acc_debit1 = frappe.db.get_value('GL Entry', {'voucher_type': 'Delivery Note', 'voucher_no': dn.name, 'account': 'Cost of Goods Sold - _TIRC'}, 'debit')
				self.assertEqual(dn_acc_debit1, qty_change[0].get("valuation_rate") * 1)
    
				from erpnext.stock.doctype.delivery_note.delivery_note import (make_sales_invoice)

				si = make_sales_invoice(dn.name)
				si.insert()
				si.submit()

				self.assertEqual(si.status, "Unpaid", "Sales Invoice not created")
    
				voucher_params_si = {
					'voucher_type': 'Sales Invoice',
					'voucher_no': si.name
				}
				gl_accounts = {
					'Sales - _TIRC': 'credit',
					'Debtors - _TIRC': 'debit',
					'Output Tax SGST - _TIRC': 'credit',
					'Output Tax CGST - _TIRC': 'credit'
				}
				gl_entries = {
					account: frappe.db.get_value('GL Entry', {**voucher_params_si, 'account': account}, field)
					for account, field in gl_accounts.items()
				}

				self.assertEqual(gl_entries['Sales - _TIRC'], 5000)
				self.assertEqual(gl_entries['Debtors - _TIRC'], 5900)
				self.assertEqual(gl_entries['Output Tax SGST - _TIRC'], 450)
				self.assertEqual(gl_entries['Output Tax CGST - _TIRC'], 450)
    
				dn.reload()
				self.assertEqual(dn.status, "Completed")
    
	def test_sales_order_partial_payment_with_gst_TC_S_012(self):
		company = frappe.get_all("Company", {"name": "_Test Indian Registered Company"}, ["gstin", "gst_category"])
		customer = frappe.get_all("Customer", {"name": "_Test Registered Customer"}, ["gstin", "gst_category"])
		company_add = frappe.get_all("Address", {"name": "_Test Indian Registered Company-Billing"}, ["name", "gstin", "gst_category"])
		customer_add = frappe.get_all("Address", {"name": "_Test Registered Customer-Billing"}, ["name", "gstin", "gst_category"])
  
		if company[0].get("gst_category") == "Registered Regular" and customer[0].get("gst_category") == "Registered Regular" and customer[0].get("gstin") and customer[0].get("gstin"):
			if company_add[0].get("gst_category") == "Registered Regular" and customer_add[0].get("gst_category") == "Registered Regular" and company_add[0].get("gstin") and customer_add[0].get("gstin"):
				so = make_sales_order(company='_Test Indian Registered Company', customer='_Test Registered Customer', warehouse='Stores - _TIRC' ,cost_center='Main - _TIRC', selling_price_list='Standard Selling', item_code='_Test Item', qty=4, rate=5000, do_not_save=True)
				so.tax_category = 'In-State'
				so.taxes_and_charges = 'Output GST In-state - _TIRC'
				so.customer_address = customer_add[0].get("name")
				so.billing_address_gstin = customer_add[0].get("gstin")
				so.company_address = company_add[0].get("name")
				so.company_gstin = company_add[0].get("gstin")
				so.save()
				so.submit()

				self.assertEqual(so.status, "To Deliver and Bill", "Sales Order not created")
				self.assertEqual(so.grand_total, so.total + so.total_taxes_and_charges)

				dn1 = make_delivery_note(so.name)
				dn1.get("items")[0].qty = 2
				dn1.save()
				dn1.submit()

				self.assertEqual(dn1.status, "To Bill", "Delivery Note not created")

				qty_change1 = frappe.get_all('Stock Ledger Entry', {'item_code': '_Test Item', 'voucher_no': dn1.name, 'warehouse': 'Stores - _TIRC'}, ['actual_qty', 'valuation_rate'])
				self.assertEqual(qty_change1[0].get("actual_qty"), -2)
    
				dn_acc_credit1 = frappe.db.get_value('GL Entry', {'voucher_type': 'Delivery Note', 'voucher_no': dn1.name, 'account': 'Stock In Hand - _TIRC'}, 'credit')
				self.assertEqual(dn_acc_credit1, qty_change1[0].get("valuation_rate") * 2)

				dn_acc_debit1 = frappe.db.get_value('GL Entry', {'voucher_type': 'Delivery Note', 'voucher_no': dn1.name, 'account': 'Cost of Goods Sold - _TIRC'}, 'debit')
				self.assertEqual(dn_acc_debit1, qty_change1[0].get("valuation_rate") * 2)
    
				from erpnext.stock.doctype.delivery_note.delivery_note import (make_sales_invoice)

				si1 = make_sales_invoice(dn1.name)
				si1.insert()
				si1.submit()

				self.assertEqual(si1.status, "Unpaid", "Sales Invoice not created")

				voucher_params_si1 = {
					'voucher_type': 'Sales Invoice',
					'voucher_no': si1.name
				}
				gl_accounts = {
					'Sales - _TIRC': 'credit',
					'Debtors - _TIRC': 'debit',
					'Output Tax SGST - _TIRC': 'credit',
					'Output Tax CGST - _TIRC': 'credit'
				}
				gl_entries_si1 = {
					account: frappe.db.get_value('GL Entry', {**voucher_params_si1, 'account': account}, field)
					for account, field in gl_accounts.items()
				}
				self.assertEqual(gl_entries_si1['Sales - _TIRC'], 10000)
				self.assertEqual(gl_entries_si1['Debtors - _TIRC'], 11800)
				self.assertEqual(gl_entries_si1['Output Tax SGST - _TIRC'], 900)
				self.assertEqual(gl_entries_si1['Output Tax CGST - _TIRC'], 900)
    
				dn1.reload()
				self.assertEqual(dn1.status, "Completed")
    
				dn2 = make_delivery_note(so.name)
				dn2.save()
				dn2.submit()

				qty_change2 = frappe.get_all('Stock Ledger Entry', {'item_code': '_Test Item', 'voucher_no': dn2.name, 'warehouse': 'Stores - _TIRC'}, ['actual_qty', 'valuation_rate'])
				self.assertEqual(qty_change2[0].get("actual_qty"), -2)
    
				dn_acc_credit2 = frappe.db.get_value('GL Entry', {'voucher_type': 'Delivery Note', 'voucher_no': dn2.name, 'account': 'Stock In Hand - _TIRC'}, 'credit')
				self.assertEqual(dn_acc_credit2, qty_change2[0].get("valuation_rate") * 2)

				dn_acc_debit2 = frappe.db.get_value('GL Entry', {'voucher_type': 'Delivery Note', 'voucher_no': dn2.name, 'account': 'Cost of Goods Sold - _TIRC'}, 'debit')
				self.assertEqual(dn_acc_debit2, qty_change2[0].get("valuation_rate") * 2)

				si2 = make_sales_invoice(dn2.name)
				si2.insert()
				si2.submit()

				self.assertEqual(si2.status, "Unpaid", "Sales Invoice not created")

				voucher_params_si2 = {
					'voucher_type': 'Sales Invoice',
					'voucher_no': si2.name
				}
				gl_accounts = {
					'Sales - _TIRC': 'credit',
					'Debtors - _TIRC': 'debit',
					'Output Tax SGST - _TIRC': 'credit',
					'Output Tax CGST - _TIRC': 'credit'
				}
				gl_entries_si2 = {
					account: frappe.db.get_value('GL Entry', {**voucher_params_si2, 'account': account}, field)
					for account, field in gl_accounts.items()
				}
				self.assertEqual(gl_entries_si2['Sales - _TIRC'], 10000)
				self.assertEqual(gl_entries_si2['Debtors - _TIRC'], 11800)
				self.assertEqual(gl_entries_si2['Output Tax SGST - _TIRC'], 900)
				self.assertEqual(gl_entries_si2['Output Tax CGST - _TIRC'], 900)
    
				dn2.reload()
				self.assertEqual(dn2.status, "Completed")
    
	def test_sales_order_partial_sales_invoice_with_gst_TC_S_013(self):
		company = frappe.get_all("Company", {"name": "_Test Indian Registered Company"}, ["gstin", "gst_category"])
		customer = frappe.get_all("Customer", {"name": "_Test Registered Customer"}, ["gstin", "gst_category"])
		company_add = frappe.get_all("Address", {"name": "_Test Indian Registered Company-Billing"}, ["name", "gstin", "gst_category"])
		customer_add = frappe.get_all("Address", {"name": "_Test Registered Customer-Billing"}, ["name", "gstin", "gst_category"])
  
		if company[0].get("gst_category") == "Registered Regular" and customer[0].get("gst_category") == "Registered Regular" and customer[0].get("gstin") and customer[0].get("gstin"):
			if company_add[0].get("gst_category") == "Registered Regular" and customer_add[0].get("gst_category") == "Registered Regular" and company_add[0].get("gstin") and customer_add[0].get("gstin"):
				so = make_sales_order(company='_Test Indian Registered Company', customer='_Test Registered Customer', warehouse='Stores - _TIRC' ,cost_center='Main - _TIRC', selling_price_list='Standard Selling', item_code='_Test Item', qty=4, rate=5000, do_not_save=True)
				so.tax_category = 'In-State'
				so.taxes_and_charges = 'Output GST In-state - _TIRC'
				so.customer_address = customer_add[0].get("name")
				so.billing_address_gstin = customer_add[0].get("gstin")
				so.company_address = company_add[0].get("name")
				so.company_gstin = company_add[0].get("gstin")
				so.save()
				so.submit()

				self.assertEqual(so.status, "To Deliver and Bill", "Sales Order not created")
				self.assertEqual(so.grand_total, so.total + so.total_taxes_and_charges)

				dn = make_delivery_note(so.name)
				dn.save()
				dn.submit()

				self.assertEqual(dn.status, "To Bill", "Delivery Note not created")

				qty_change = frappe.get_all('Stock Ledger Entry', {'item_code': '_Test Item', 'voucher_no': dn.name, 'warehouse': 'Stores - _TIRC'}, ['actual_qty', 'valuation_rate'])
				self.assertEqual(qty_change[0].get("actual_qty"), -4)
    
				dn_acc_credit1 = frappe.db.get_value('GL Entry', {'voucher_type': 'Delivery Note', 'voucher_no': dn.name, 'account': 'Stock In Hand - _TIRC'}, 'credit')
				self.assertEqual(dn_acc_credit1, qty_change[0].get("valuation_rate") * 4)

				dn_acc_debit1 = frappe.db.get_value('GL Entry', {'voucher_type': 'Delivery Note', 'voucher_no': dn.name, 'account': 'Cost of Goods Sold - _TIRC'}, 'debit')
				self.assertEqual(dn_acc_debit1, qty_change[0].get("valuation_rate") * 4)
    
				from erpnext.stock.doctype.delivery_note.delivery_note import (make_sales_invoice)

				si1 = make_sales_invoice(dn.name)
				si1.get("items")[0].qty = 2
				si1.insert()
				si1.submit()

				self.assertEqual(si1.status, "Unpaid", "Sales Invoice not created")

				voucher_params_si1 = {
					'voucher_type': 'Sales Invoice',
					'voucher_no': si1.name
				}
				gl_accounts = {
					'Sales - _TIRC': 'credit',
					'Debtors - _TIRC': 'debit',
					'Output Tax SGST - _TIRC': 'credit',
					'Output Tax CGST - _TIRC': 'credit'
				}
				gl_entries_si1 = {
					account: frappe.db.get_value('GL Entry', {**voucher_params_si1, 'account': account}, field)
					for account, field in gl_accounts.items()
				}
				self.assertEqual(gl_entries_si1['Sales - _TIRC'], 10000)
				self.assertEqual(gl_entries_si1['Debtors - _TIRC'], 11800)
				self.assertEqual(gl_entries_si1['Output Tax SGST - _TIRC'], 900)
				self.assertEqual(gl_entries_si1['Output Tax CGST - _TIRC'], 900)
    
				si2 = make_sales_invoice(dn.name)
				si2.insert()
				si2.submit()

				self.assertEqual(si2.status, "Unpaid", "Sales Invoice not created")

				voucher_params_si2 = {
					'voucher_type': 'Sales Invoice',
					'voucher_no': si2.name
				}
				gl_accounts = {
					'Sales - _TIRC': 'credit',
					'Debtors - _TIRC': 'debit',
					'Output Tax SGST - _TIRC': 'credit',
					'Output Tax CGST - _TIRC': 'credit'
				}
				gl_entries_si2 = {
					account: frappe.db.get_value('GL Entry', {**voucher_params_si2, 'account': account}, field)
					for account, field in gl_accounts.items()
				}
				self.assertEqual(gl_entries_si2['Sales - _TIRC'], 10000)
				self.assertEqual(gl_entries_si2['Debtors - _TIRC'], 11800)
				self.assertEqual(gl_entries_si2['Output Tax SGST - _TIRC'], 900)
				self.assertEqual(gl_entries_si2['Output Tax CGST - _TIRC'], 900)
    
				dn.reload()
				self.assertEqual(dn.status, "Completed")
    
	def test_sales_order_create_dn_via_si_with_gst_TC_S_014(self):
		company = frappe.get_all("Company", {"name": "_Test Indian Registered Company"}, ["gstin", "gst_category"])
		customer = frappe.get_all("Customer", {"name": "_Test Registered Customer"}, ["gstin", "gst_category"])
		company_add = frappe.get_all("Address", {"name": "_Test Indian Registered Company-Billing"}, ["name", "gstin", "gst_category"])
		customer_add = frappe.get_all("Address", {"name": "_Test Registered Customer-Billing"}, ["name", "gstin", "gst_category"])
  
		if company[0].get("gst_category") == "Registered Regular" and customer[0].get("gst_category") == "Registered Regular" and customer[0].get("gstin") and customer[0].get("gstin"):
			if company_add[0].get("gst_category") == "Registered Regular" and customer_add[0].get("gst_category") == "Registered Regular" and company_add[0].get("gstin") and customer_add[0].get("gstin"):
				so = make_sales_order(company='_Test Indian Registered Company', customer='_Test Registered Customer', warehouse='Stores - _TIRC' ,cost_center='Main - _TIRC', selling_price_list='Standard Selling', item_code='_Test Item', qty=4, rate=5000, do_not_save=True)
				so.tax_category = 'In-State'
				so.taxes_and_charges = 'Output GST In-state - _TIRC'
				so.customer_address = customer_add[0].get("name")
				so.billing_address_gstin = customer_add[0].get("gstin")
				so.company_address = company_add[0].get("name")
				so.company_gstin = company_add[0].get("gstin")
				so.save()
				so.submit()

				self.assertEqual(so.status, "To Deliver and Bill", "Sales Order not created")
				self.assertEqual(so.grand_total, so.total + so.total_taxes_and_charges)
    
				si = make_sales_invoice(so.name)
				si.save()
				si.submit()

				self.assertEqual(si.status, "Unpaid", "Sales Invoice not created")
    
				si_acc_credit = frappe.db.get_value('GL Entry', {'voucher_type': 'Sales Invoice', 'voucher_no': si.name, 'account': 'Sales - _TIRC'}, 'credit')
				self.assertEqual(si_acc_credit, 20000)

				si_acc_debit = frappe.db.get_value('GL Entry', {'voucher_type': 'Sales Invoice', 'voucher_no': si.name, 'account': 'Debtors - _TIRC'}, 'debit')
				self.assertEqual(si_acc_debit, 23600)
    
				si_acc_credit_gst = frappe.db.get_value('GL Entry', {'voucher_type': 'Sales Invoice', 'voucher_no': si.name, 'account': 'Output Tax SGST - _TIRC'}, 'credit')
				self.assertEqual(si_acc_credit_gst, 1800)

				si_acc_debit_gst = frappe.db.get_value('GL Entry', {'voucher_type': 'Sales Invoice', 'voucher_no': si.name, 'account': 'Output Tax CGST - _TIRC'}, 'credit')
				self.assertEqual(si_acc_debit_gst, 1800)			
    
				from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_delivery_note
				dn = make_delivery_note(si.name)
				dn.save()
				dn.submit()

				self.assertEqual(dn.status, "Completed", "Delivery Note not created")

				qty_change = frappe.get_all('Stock Ledger Entry', {'item_code': '_Test Item', 'voucher_no': dn.name, 'warehouse': 'Stores - _TIRC'}, ['actual_qty', 'valuation_rate'])
				self.assertEqual(qty_change[0].get("actual_qty"), -4)

				dn_acc_credit = frappe.db.get_value('GL Entry', {'voucher_type': 'Delivery Note', 'voucher_no': dn.name, 'account': 'Stock In Hand - _TIRC'}, 'credit')
				self.assertEqual(dn_acc_credit, qty_change[0].get("valuation_rate") * 4)

				dn_acc_debit = frappe.db.get_value('GL Entry', {'voucher_type': 'Delivery Note', 'voucher_no': dn.name, 'account': 'Cost of Goods Sold - _TIRC'}, 'debit')
				self.assertEqual(dn_acc_debit, qty_change[0].get("valuation_rate") * 4)
    
	def test_sales_order_create_partial_dn_via_si_with_gst_TC_S_015(self):
		company = frappe.get_all("Company", {"name": "_Test Indian Registered Company"}, ["gstin", "gst_category"])
		customer = frappe.get_all("Customer", {"name": "_Test Registered Customer"}, ["gstin", "gst_category"])
		company_add = frappe.get_all("Address", {"name": "_Test Indian Registered Company-Billing"}, ["name", "gstin", "gst_category"])
		customer_add = frappe.get_all("Address", {"name": "_Test Registered Customer-Billing"}, ["name", "gstin", "gst_category"])
  
		if company[0].get("gst_category") == "Registered Regular" and customer[0].get("gst_category") == "Registered Regular" and customer[0].get("gstin") and customer[0].get("gstin"):
			if company_add[0].get("gst_category") == "Registered Regular" and customer_add[0].get("gst_category") == "Registered Regular" and company_add[0].get("gstin") and customer_add[0].get("gstin"):
				so = make_sales_order(company='_Test Indian Registered Company', customer='_Test Registered Customer', warehouse='Stores - _TIRC' ,cost_center='Main - _TIRC', selling_price_list='Standard Selling', item_code='_Test Item', qty=4, rate=5000, do_not_save=True)
				so.tax_category = 'In-State'
				so.taxes_and_charges = 'Output GST In-state - _TIRC'
				so.customer_address = customer_add[0].get("name")
				so.billing_address_gstin = customer_add[0].get("gstin")
				so.company_address = company_add[0].get("name")
				so.company_gstin = company_add[0].get("gstin")
				so.save()
				so.submit()

				self.assertEqual(so.status, "To Deliver and Bill", "Sales Order not created")
				self.assertEqual(so.grand_total, so.total + so.total_taxes_and_charges)
    
				si = make_sales_invoice(so.name)
				si.save()
				si.submit()

				self.assertEqual(si.status, "Unpaid", "Sales Invoice not created")
    
				voucher_params_si = {
					'voucher_type': 'Sales Invoice',
					'voucher_no': si.name
				}
				gl_accounts = {
					'Sales - _TIRC': 'credit',
					'Debtors - _TIRC': 'debit',
					'Output Tax SGST - _TIRC': 'credit',
					'Output Tax CGST - _TIRC': 'credit'
				}
				gl_entries = {
					account: frappe.db.get_value('GL Entry', {**voucher_params_si, 'account': account}, field)
					for account, field in gl_accounts.items()
				}
				self.assertEqual(gl_entries['Sales - _TIRC'], 20000)
				self.assertEqual(gl_entries['Debtors - _TIRC'], 23600)
				self.assertEqual(gl_entries['Output Tax SGST - _TIRC'], 1800)
				self.assertEqual(gl_entries['Output Tax CGST - _TIRC'], 1800)		
    
				from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_delivery_note
				dn1 = make_delivery_note(si.name)
				dn1.get("items")[0].qty = 2
				dn1.save()
				dn1.submit()

				self.assertEqual(dn1.status, "Completed", "Delivery Note not created")

				qty_change1 = frappe.get_all(
					'Stock Ledger Entry',
					{'item_code': '_Test Item', 'voucher_no': dn1.name, 'warehouse': 'Stores - _TIRC'},
					['actual_qty', 'valuation_rate']
				)
				actual_qty = qty_change1[0].get("actual_qty")
				valuation_rate = qty_change1[0].get("valuation_rate")

				self.assertEqual(actual_qty, -2)

				voucher_params_dn1 = {
					'voucher_type': 'Delivery Note','voucher_no': dn1.name
				}
				gl_accounts_dn1 = {
					'Stock In Hand - _TIRC': 'credit','Cost of Goods Sold - _TIRC': 'debit'
				}
				gl_entries_dn1 = {
					account: frappe.db.get_value('GL Entry', {**voucher_params_dn1, 'account': account}, field)
					for account, field in gl_accounts_dn1.items()
				}
				self.assertEqual(gl_entries_dn1['Stock In Hand - _TIRC'], valuation_rate * 2)
				self.assertEqual(gl_entries_dn1['Cost of Goods Sold - _TIRC'], valuation_rate * 2)
    
				dn2 = make_delivery_note(si.name)
				dn2.save()
				dn2.submit()
    
				self.assertEqual(dn1.status, "Completed", "Delivery Note not created")

				qty_change2 = frappe.get_all(
					'Stock Ledger Entry',
					{'item_code': '_Test Item', 'voucher_no': dn2.name, 'warehouse': 'Stores - _TIRC'},
					['actual_qty', 'valuation_rate']
				)
				actual_qty = qty_change2[0].get("actual_qty")
				valuation_rate = qty_change2[0].get("valuation_rate")

				self.assertEqual(actual_qty, -2)

				voucher_params_dn2 = {
					'voucher_type': 'Delivery Note',
					'voucher_no': dn2.name
				}
				gl_accounts_dn2 = {
					'Stock In Hand - _TIRC': 'credit',
					'Cost of Goods Sold - _TIRC': 'debit'
				}
				gl_entries_dn2 = {
					account: frappe.db.get_value('GL Entry', {**voucher_params_dn2, 'account': account}, field)
					for account, field in gl_accounts_dn2.items()
				}
				self.assertEqual(gl_entries_dn2['Stock In Hand - _TIRC'], valuation_rate * 2)
				self.assertEqual(gl_entries_dn2['Cost of Goods Sold - _TIRC'], valuation_rate * 2)
    
	def test_sales_order_update_stock_in_si_with_gst_TC_S_018(self):
		company = frappe.get_all("Company", {"name": "_Test Indian Registered Company"}, ["gstin", "gst_category"])
		customer = frappe.get_all("Customer", {"name": "_Test Registered Customer"}, ["gstin", "gst_category"])
		company_add = frappe.get_all("Address", {"name": "_Test Indian Registered Company-Billing"}, ["name", "gstin", "gst_category"])
		customer_add = frappe.get_all("Address", {"name": "_Test Registered Customer-Billing"}, ["name", "gstin", "gst_category"])
  
		if company[0].get("gst_category") == "Registered Regular" and customer[0].get("gst_category") == "Registered Regular" and customer[0].get("gstin") and customer[0].get("gstin"):
			if company_add[0].get("gst_category") == "Registered Regular" and customer_add[0].get("gst_category") == "Registered Regular" and company_add[0].get("gstin") and customer_add[0].get("gstin"):
				so = make_sales_order(company='_Test Indian Registered Company', customer='_Test Registered Customer', warehouse='Stores - _TIRC' ,cost_center='Main - _TIRC', selling_price_list='Standard Selling', item_code='_Test Item', qty=4, rate=5000, do_not_save=True)
				so.tax_category = 'In-State'
				so.taxes_and_charges = 'Output GST In-state - _TIRC'
				so.customer_address = customer_add[0].get("name")
				so.billing_address_gstin = customer_add[0].get("gstin")
				so.company_address = company_add[0].get("name")
				so.company_gstin = company_add[0].get("gstin")
				so.save()
				so.submit()

				self.assertEqual(so.status, "To Deliver and Bill", "Sales Order not created")
				self.assertEqual(so.grand_total, so.total + so.total_taxes_and_charges)

				si = make_sales_invoice(so.name)
				si.update_stock = 1
				si.save()
				si.submit()

				self.assertEqual(si.status, "Unpaid", "Sales Invoice not created")

				qty_change = frappe.get_all(
					'Stock Ledger Entry',
					{'item_code': '_Test Item', 'voucher_no': si.name, 'warehouse': 'Stores - _TIRC'},
					['actual_qty', 'valuation_rate']
				)
				actual_qty = qty_change[0].get("actual_qty")
				valuation_rate = qty_change[0].get("valuation_rate")

				self.assertEqual(actual_qty, -4)

				voucher_params_si = {
					'voucher_type': 'Sales Invoice',
					'voucher_no': si.name
				}
				gl_accounts_si = {
					'Stock In Hand - _TIRC': 'credit',
					'Cost of Goods Sold - _TIRC': 'debit',
					'Sales - _TIRC': 'credit',
					'Debtors - _TIRC': 'debit',
					'Output Tax SGST - _TIRC': 'credit',
					'Output Tax CGST - _TIRC': 'credit'
				}
				gl_entries_si = {
					account: frappe.db.get_value('GL Entry', {**voucher_params_si, 'account': account}, field)
					for account, field in gl_accounts_si.items()
				}
				self.assertEqual(gl_entries_si['Stock In Hand - _TIRC'], valuation_rate * 4)
				self.assertEqual(gl_entries_si['Cost of Goods Sold - _TIRC'], valuation_rate * 4)
				self.assertEqual(gl_entries_si['Sales - _TIRC'], 20000)
				self.assertEqual(gl_entries_si['Debtors - _TIRC'], 23600)
				self.assertEqual(gl_entries_si['Output Tax SGST - _TIRC'], 1800)
				self.assertEqual(gl_entries_si['Output Tax CGST - _TIRC'], 1800)

				so.reload()
				self.assertEqual(so.status, 'Completed')
    
	def test_sales_order_update_stock_in_partial_si_with_gst_TC_S_019(self):
		company = frappe.get_all("Company", {"name": "_Test Indian Registered Company"}, ["gstin", "gst_category"])
		customer = frappe.get_all("Customer", {"name": "_Test Registered Customer"}, ["gstin", "gst_category"])
		company_add = frappe.get_all("Address", {"name": "_Test Indian Registered Company-Billing"}, ["name", "gstin", "gst_category"])
		customer_add = frappe.get_all("Address", {"name": "_Test Registered Customer-Billing"}, ["name", "gstin", "gst_category"])
  
		if company[0].get("gst_category") == "Registered Regular" and customer[0].get("gst_category") == "Registered Regular" and customer[0].get("gstin") and customer[0].get("gstin"):
			if company_add[0].get("gst_category") == "Registered Regular" and customer_add[0].get("gst_category") == "Registered Regular" and company_add[0].get("gstin") and customer_add[0].get("gstin"):
				so = make_sales_order(company='_Test Indian Registered Company', customer='_Test Registered Customer', warehouse='Stores - _TIRC' ,cost_center='Main - _TIRC', selling_price_list='Standard Selling', item_code='_Test Item', qty=4, rate=5000, do_not_save=True)
				so.tax_category = 'In-State'
				so.taxes_and_charges = 'Output GST In-state - _TIRC'
				so.customer_address = customer_add[0].get("name")
				so.billing_address_gstin = customer_add[0].get("gstin")
				so.company_address = company_add[0].get("name")
				so.company_gstin = company_add[0].get("gstin")
				so.save()
				so.submit()

				self.assertEqual(so.status, "To Deliver and Bill", "Sales Order not created")
				self.assertEqual(so.grand_total, so.total + so.total_taxes_and_charges)

				si1 = make_sales_invoice(so.name)
				si1.get("items")[0].qty = 2
				si1.update_stock = 1
				si1.save()
				si1.submit()

				self.assertEqual(si1.status, "Unpaid", "Sales Invoice not created")

				qty_change1 = frappe.get_all(
					'Stock Ledger Entry',
					{'item_code': '_Test Item', 'voucher_no': si1.name, 'warehouse': 'Stores - _TIRC'},
					['actual_qty', 'valuation_rate']
				)

				actual_qty1 = qty_change1[0].get("actual_qty")
				valuation_rate1 = qty_change1[0].get("valuation_rate")

				self.assertEqual(actual_qty1, -2)

				voucher_params_si1 = {
					'voucher_type': 'Sales Invoice','voucher_no': si1.name
				}
				gl_accounts_si1 = {
					'Stock In Hand - _TIRC': 'credit',
					'Cost of Goods Sold - _TIRC': 'debit',
					'Sales - _TIRC': 'credit',
					'Debtors - _TIRC': 'debit'
				}
				gl_entries_si1 = {
					account: frappe.db.get_value('GL Entry', {**voucher_params_si1, 'account': account}, field)
					for account, field in gl_accounts_si1.items()
				}
				self.assertEqual(gl_entries_si1['Stock In Hand - _TIRC'], valuation_rate1 * 2)
				self.assertEqual(gl_entries_si1['Cost of Goods Sold - _TIRC'], valuation_rate1 * 2)
				self.assertEqual(gl_entries_si1['Sales - _TIRC'], 10000)
				self.assertEqual(gl_entries_si1['Debtors - _TIRC'], 11800)
		
				si2 = make_sales_invoice(so.name)
				si2.update_stock = 1
				si2.save()
				si2.submit()

				self.assertEqual(si2.status, "Unpaid", "Sales Invoice not created")

				qty_change2 = frappe.get_all(
					'Stock Ledger Entry',
					{'item_code': '_Test Item', 'voucher_no': si2.name, 'warehouse': 'Stores - _TIRC'},
					['actual_qty', 'valuation_rate']
				)
				actual_qty2 = qty_change2[0].get("actual_qty")
				valuation_rate2 = qty_change2[0].get("valuation_rate")

				self.assertEqual(actual_qty2, -2)

				voucher_params_si2 = {
					'voucher_type': 'Sales Invoice','voucher_no': si2.name
				}
				gl_accounts_si2 = {
					'Stock In Hand - _TIRC': 'credit',
					'Cost of Goods Sold - _TIRC': 'debit',
					'Sales - _TIRC': 'credit',
					'Debtors - _TIRC': 'debit'
				}
				gl_entries_si2 = {
					account: frappe.db.get_value('GL Entry', {**voucher_params_si2, 'account': account}, field)
					for account, field in gl_accounts_si2.items()
				}
				self.assertEqual(gl_entries_si2['Stock In Hand - _TIRC'], valuation_rate2 * 2)
				self.assertEqual(gl_entries_si2['Cost of Goods Sold - _TIRC'], valuation_rate2 * 2)
				self.assertEqual(gl_entries_si2['Sales - _TIRC'], 10000)
				self.assertEqual(gl_entries_si2['Debtors - _TIRC'], 11800)

				so.reload()
				self.assertEqual(so.status, 'Completed')
    
	def test_sales_order_for_service_item_with_gst_TC_S_020(self):
		make_service_item()
		company = frappe.get_all("Company", {"name": "_Test Indian Registered Company"}, ["gstin", "gst_category"])
		customer = frappe.get_all("Customer", {"name": "_Test Registered Customer"}, ["gstin", "gst_category"])
		company_add = frappe.get_all("Address", {"name": "_Test Indian Registered Company-Billing"}, ["name", "gstin", "gst_category"])
		customer_add = frappe.get_all("Address", {"name": "_Test Registered Customer-Billing"}, ["name", "gstin", "gst_category"])
  
		if company[0].get("gst_category") == "Registered Regular" and customer[0].get("gst_category") == "Registered Regular" and customer[0].get("gstin") and customer[0].get("gstin"):
			if company_add[0].get("gst_category") == "Registered Regular" and customer_add[0].get("gst_category") == "Registered Regular" and company_add[0].get("gstin") and customer_add[0].get("gstin"):
				so = make_sales_order(company='_Test Indian Registered Company', customer='_Test Registered Customer', warehouse='Stores - _TIRC' ,cost_center='Main - _TIRC', selling_price_list='Standard Selling', item_code='Consultancy', qty=1, rate=5000, do_not_save=True)
				so.tax_category = 'In-State'
				so.taxes_and_charges = 'Output GST In-state - _TIRC'
				so.customer_address = customer_add[0].get("name")
				so.billing_address_gstin = customer_add[0].get("gstin")
				so.company_address = company_add[0].get("name")
				so.company_gstin = company_add[0].get("gstin")
				so.save()
				so.submit()

				self.assertEqual(so.status, "To Deliver and Bill", "Sales Order not created")
				self.assertEqual(so.grand_total, so.total + so.total_taxes_and_charges)
		
				si = make_sales_invoice(so.name)
				si.save()
				si.submit()

				self.assertEqual(si.status, "Unpaid", "Sales Invoice not created")
		
				voucher_params_si = {
					'voucher_type': 'Sales Invoice','voucher_no': si.name
				}
				gl_accounts_si = {
					'Sales - _TIRC': 'credit',
					'Debtors - _TIRC': 'debit',
					'Output Tax SGST - _TIRC': 'credit',
					'Output Tax CGST - _TIRC': 'credit'
				}
				gl_entries_si = {
					account: frappe.db.get_value('GL Entry', {**voucher_params_si, 'account': account}, field)
					for account, field in gl_accounts_si.items()
				}
				self.assertEqual(gl_entries_si['Sales - _TIRC'], 5000)
				self.assertEqual(gl_entries_si['Debtors - _TIRC'], 5900)
				self.assertEqual(gl_entries_si['Output Tax SGST - _TIRC'], 450)
				self.assertEqual(gl_entries_si['Output Tax CGST - _TIRC'], 450)
    
	def test_sales_order_of_full_payment_with_shipping_rule_TC_S_021(self):
		so = make_sales_order(cost_center='Main - _TC', selling_price_list='Standard Selling', qty=1, rate=5000, do_not_save=True)
		so.shipping_rule = "_Test Shipping Rule"
		so.save()
		so.submit()

		self.assertEqual(so.status, "To Deliver and Bill", "Sales Order not created")
		self.assertEqual(so.grand_total, so.total + so.total_taxes_and_charges)
  
		dn = make_delivery_note(so.name)
		dn.save()
		dn.submit()
  
		self.assertEqual(dn.status, "To Bill", "Delivery Note not created")
  
		qty_change = frappe.get_all('Stock Ledger Entry', {'item_code': '_Test Item', 'voucher_no': dn.name, 'warehouse': '_Test Warehouse - _TC'}, ['actual_qty', 'valuation_rate'])
		self.assertEqual(qty_change[0].get("actual_qty"), -1)
		
		from erpnext.stock.doctype.delivery_note.delivery_note import (make_sales_invoice)
  
		si = make_sales_invoice(dn.name)
		si.save()
		si.submit()
    
		voucher_params_si = {
			'voucher_type': 'Sales Invoice','voucher_no': si.name
		}
		gl_accounts_si = {
			'Sales - _TC': 'credit',
			'Debtors - _TC': 'debit',
			'_Test Account Shipping Charges - _TC': 'credit'
		}
		gl_entries_si = {
			account: frappe.db.get_value('GL Entry', {**voucher_params_si, 'account': account}, field)
			for account, field in gl_accounts_si.items()
		}
		self.assertEqual(gl_entries_si['Sales - _TC'], 5000)
		self.assertEqual(gl_entries_si['Debtors - _TC'], 5200)
		self.assertEqual(gl_entries_si['_Test Account Shipping Charges - _TC'], 200)
  
	def test_sales_order_for_partial_delivery_with_shipping_rule_TC_S_022(self):
		so = make_sales_order(cost_center='Main - _TC', selling_price_list='Standard Selling', qty=4, rate=5000, do_not_save=True)
		so.shipping_rule = "_Test Shipping Rule"
		so.save()
		so.submit()

		self.assertEqual(so.status, "To Deliver and Bill", "Sales Order not created")
		self.assertEqual(so.grand_total, so.total + so.total_taxes_and_charges)

		dn1 = make_delivery_note(so.name)
		dn1.items[0].qty = 2
		dn1.save()
		dn1.submit()

		self.assertEqual(dn1.status, "To Bill", "Delivery Note not created")

		qty_change1 = frappe.get_all('Stock Ledger Entry', {'item_code': '_Test Item', 'voucher_no': dn1.name, 'warehouse': '_Test Warehouse - _TC'}, ['actual_qty', 'valuation_rate'])
		self.assertEqual(qty_change1[0].get("actual_qty"), -2)

		from erpnext.stock.doctype.delivery_note.delivery_note import (make_sales_invoice)

		si1 = make_sales_invoice(dn1.name)
		si1.save()
		si1.submit()

		self.assertEqual(si1.status, "Unpaid", "Sales Invoice not created")

		voucher_params_si1 = {
			'voucher_type': 'Sales Invoice','voucher_no': si1.name
		}
  
		gl_accounts_si1 = {
			'Sales - _TC': 'credit',
			'Debtors - _TC': 'debit',
			'_Test Account Shipping Charges - _TC': 'credit'
		}
		gl_entries_si1 = {
			account: frappe.db.get_value('GL Entry', {**voucher_params_si1, 'account': account}, field)
			for account, field in gl_accounts_si1.items()
		}
		self.assertEqual(gl_entries_si1['Sales - _TC'], 10000)
		self.assertEqual(gl_entries_si1['Debtors - _TC'], 10200)
		self.assertEqual(gl_entries_si1['_Test Account Shipping Charges - _TC'], 200)

		dn2 = make_delivery_note(so.name)
		dn2.save()
		dn2.submit()

		self.assertEqual(dn2.status, "To Bill", "Delivery Note not created")

		qty_change2 = frappe.get_all('Stock Ledger Entry', {'item_code': '_Test Item', 'voucher_no': dn2.name, 'warehouse': '_Test Warehouse - _TC'}, ['actual_qty', 'valuation_rate'])
		self.assertEqual(qty_change2[0].get("actual_qty"), -2)

		si2 = make_sales_invoice(dn2.name)
		si2.save()
		si2.submit()

		self.assertEqual(si2.status, "Unpaid", "Sales Invoice not created")

		voucher_params_si2 = {
			'voucher_type': 'Sales Invoice', 'voucher_no': si2.name
		}
		gl_accounts_si2 = {
			'Sales - _TC': 'credit',
			'Debtors - _TC': 'debit',
			'_Test Account Shipping Charges - _TC': 'credit'
		}
		gl_entries_si2 = {
			account: frappe.db.get_value('GL Entry', {**voucher_params_si2, 'account': account}, field)
			for account, field in gl_accounts_si2.items()
		}
		self.assertEqual(gl_entries_si2['Sales - _TC'], 10000)
		self.assertEqual(gl_entries_si2['Debtors - _TC'], 10200)
		self.assertEqual(gl_entries_si2['_Test Account Shipping Charges - _TC'], 200)
  
	def test_sales_order_for_partial_invoice_with_shipping_rule_TC_S_023(self):
		so = make_sales_order(cost_center='Main - _TC', selling_price_list='Standard Selling', qty=4, rate=5000, do_not_save=True)
		so.shipping_rule = "_Test Shipping Rule"
		so.save()
		so.submit()

		self.assertEqual(so.status, "To Deliver and Bill", "Sales Order not created")
		self.assertEqual(so.grand_total, so.total + so.total_taxes_and_charges)

		dn = make_delivery_note(so.name)
		dn.save()
		dn.submit()

		self.assertEqual(dn.status, "To Bill", "Delivery Note not created")

		qty_change = frappe.get_all('Stock Ledger Entry', {'item_code': '_Test Item', 'voucher_no': dn.name, 'warehouse': '_Test Warehouse - _TC'}, ['actual_qty', 'valuation_rate'])
		self.assertEqual(qty_change[0].get("actual_qty"), -4)

		from erpnext.stock.doctype.delivery_note.delivery_note import (make_sales_invoice)

		si1 = make_sales_invoice(dn.name)
		si1.items[0].qty = 2
		si1.save()
		si1.submit()

		self.assertEqual(si1.status, "Unpaid", "Sales Invoice not created")

		voucher_params_si1 = {
			'voucher_type': 'Sales Invoice', 'voucher_no': si1.name
		}
		gl_accounts_si1 = {
			'Sales - _TC': 'credit',
			'Debtors - _TC': 'debit',
			'_Test Account Shipping Charges - _TC': 'credit'
		}
		gl_entries_si1 = {
			account: frappe.db.get_value('GL Entry', {**voucher_params_si1, 'account': account}, field)
			for account, field in gl_accounts_si1.items()
		}
		self.assertEqual(gl_entries_si1['Sales - _TC'], 10000)
		self.assertEqual(gl_entries_si1['Debtors - _TC'], 10200)
		self.assertEqual(gl_entries_si1['_Test Account Shipping Charges - _TC'], 200)

		si2 = make_sales_invoice(dn.name)
		si2.save()
		si2.submit()

		self.assertEqual(si2.status, "Unpaid", "Sales Invoice not created")

		voucher_params_si2 = {
			'voucher_type': 'Sales Invoice', 'voucher_no': si2.name
		}
		gl_accounts_si2 = {
			'Sales - _TC': 'credit',
			'Debtors - _TC': 'debit',
			'_Test Account Shipping Charges - _TC': 'credit'
		}
		gl_entries_si2 = {
			account: frappe.db.get_value('GL Entry', {**voucher_params_si2, 'account': account}, field)
			for account, field in gl_accounts_si2.items()
		}
		self.assertEqual(gl_entries_si2['Sales - _TC'], 10000)
		self.assertEqual(gl_entries_si2['Debtors - _TC'], 10200)
		self.assertEqual(gl_entries_si2['_Test Account Shipping Charges - _TC'], 200)
  
	def test_sales_order_via_sales_invoice_with_shipping_rule_TC_S_024(self):
		so = make_sales_order(cost_center='Main - _TC', selling_price_list='Standard Selling', qty=4, rate=5000, do_not_save=True)
		so.shipping_rule = "_Test Shipping Rule"
		so.save()
		so.submit()

		self.assertEqual(so.status, "To Deliver and Bill", "Sales Order not created")
		self.assertEqual(so.grand_total, so.total + so.total_taxes_and_charges)

		si = make_sales_invoice(so.name)
		si.save()
		si.submit()

		self.assertEqual(si.status, "Unpaid", "Sales Invoice not created")

		voucher_params_si = {
			'voucher_type': 'Sales Invoice', 'voucher_no': si.name
		}
		gl_accounts_si = {
			'Sales - _TC': 'credit',
			'Debtors - _TC': 'debit',
			'_Test Account Shipping Charges - _TC': 'credit'
		}
		gl_entries_si = {
			account: frappe.db.get_value('GL Entry', {**voucher_params_si, 'account': account}, field)
			for account, field in gl_accounts_si.items()
		}
		self.assertEqual(gl_entries_si['Sales - _TC'], 20000)
		self.assertEqual(gl_entries_si['Debtors - _TC'], 20200)
		self.assertEqual(gl_entries_si['_Test Account Shipping Charges - _TC'], 200)

		from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_delivery_note
		dn = make_delivery_note(si.name)
		dn.save()
		dn.submit()

		self.assertEqual(dn.status, "Completed", "Delivery Note not created")

		qty_change = frappe.get_all('Stock Ledger Entry', {'item_code': '_Test Item', 'voucher_no': dn.name, 'warehouse': '_Test Warehouse - _TC'}, ['actual_qty', 'valuation_rate'])
		self.assertEqual(qty_change[0].get("actual_qty"), -4)
  
	def test_sales_order_for_partial_dn_via_si_for_service_item_TC_S_025(self):
		so = make_sales_order(cost_center='Main - _TC', selling_price_list='Standard Selling', qty=4, rate=5000, do_not_save=True)
		so.shipping_rule = "_Test Shipping Rule"
		so.save()
		so.submit()

		self.assertEqual(so.status, "To Deliver and Bill", "Sales Order not created")
		self.assertEqual(so.grand_total, so.total + so.total_taxes_and_charges)

		si = make_sales_invoice(so.name)
		si.save()
		si.submit()

		self.assertEqual(si.status, "Unpaid", "Sales Invoice not created")

		voucher_params_si = {
			'voucher_type': 'Sales Invoice', 'voucher_no': si.name
		}
		gl_accounts_si = {
			'Sales - _TC': 'credit',
			'Debtors - _TC': 'debit',
			'_Test Account Shipping Charges - _TC': 'credit'
		}
		gl_entries_si = {
			account: frappe.db.get_value('GL Entry', {**voucher_params_si, 'account': account}, field)
			for account, field in gl_accounts_si.items()
		}
		self.assertEqual(gl_entries_si['Sales - _TC'], 20000)
		self.assertEqual(gl_entries_si['Debtors - _TC'], 20200)
		self.assertEqual(gl_entries_si['_Test Account Shipping Charges - _TC'], 200)

		from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_delivery_note
		dn1 = make_delivery_note(si.name)
		dn1.get("items")[0].qty = 2
		dn1.save()
		dn1.submit()

		self.assertEqual(dn1.status, "Completed", "Delivery Note not created")

		qty_change = frappe.get_all('Stock Ledger Entry', {'item_code': '_Test Item', 'voucher_no': dn1.name, 'warehouse': '_Test Warehouse - _TC'}, ['actual_qty', 'valuation_rate'])
		self.assertEqual(qty_change[0].get("actual_qty"), -2)
  
		dn2 = make_delivery_note(si.name)
		dn2.save()
		dn2.submit()

		self.assertEqual(dn2.status, "Completed", "Delivery Note not created")

		qty_change2 = frappe.get_all('Stock Ledger Entry', {'item_code': '_Test Item', 'voucher_no': dn2.name, 'warehouse': '_Test Warehouse - _TC'}, ['actual_qty', 'valuation_rate'])
		self.assertEqual(qty_change2[0].get("actual_qty"), -2)

	def test_so_with_qi_flow_TC_S_032(self):
		from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note
		from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_invoice
		from erpnext.stock.doctype.quality_inspection.test_quality_inspection import create_quality_inspection

		item = frappe.get_doc({
			"doctype": "Item",
			"item_code": "_Test Item for quality inspection",
			"item_name": "_Test Item for quality inspection",
			"stock_uom": "Nos",
			"is_stock_item": 1,
			"opening_stock": 1000,
			"valuation_rate": 100,
			"inspection_required_before_delivery": 1,
			"gst_hsn_code": "90183100"
		}).insert()

		parameters = ["_Test Needle Shape", "_Test Syringe Shape", "_Test Plastic Clarity", "_Test Syringe Length"]
		for param in parameters:
			frappe.get_doc({
				"doctype": "Quality Inspection Parameter",
				"parameter": param
			}).insert()

		template = frappe.get_doc({
			"doctype": "Quality Inspection Template",
			"quality_inspection_template_name": "_Test Syringe",
			"item_quality_inspection_parameter": [
				{"specification": "_Test Needle Shape", "value": "OK"},
				{"specification": "_Test Syringe Shape", "value": "OK"},
				{"specification": "_Test Plastic Clarity", "value": "OK"},
				{"specification": "_Test Syringe Length", "numeric": 1, "min_value": 4, "max_value": 6}
			]
		}).insert()

		frappe.db.set_value("Item", item.name, "quality_inspection_template", template.name)
		item.reload()

		sales_order = make_sales_order(item_code=item.name, qty=5, rate=200)

		delivery_note = make_delivery_note(sales_order.name)
		delivery_note.save()
		
		with self.assertRaises(frappe.ValidationError):
			delivery_note.submit()
		
		quality_inspection = create_quality_inspection(
			reference_type="Delivery Note", 
			reference_name=delivery_note.name,
			item_code=item.name,
			do_not_save=True,
			readings=[
				{"specification": "_Test Needle Shape", "value": "OK"},
				{"specification": "_Test Syringe Shape", "value": "OK"},
				{"specification": "_Test Plastic Clarity", "value": "OK"},
				{"specification": "_Test Syringe Length", "numeric": 1, "reading_1": 5, "manual_inspection": 1}
			]
		)
		self.assertEqual(quality_inspection.status, "Accepted")

		quality_inspection.child_row_reference = True
		quality_inspection.save()
		quality_inspection.submit()

		delivery_note.reload()
		delivery_note.submit()

		self.assertEqual(delivery_note.status, "To Bill")
		
		stock_entry = frappe.get_doc({
			"doctype": "Stock Ledger Entry",
			"item_code": item.name,
			"qty": -5,
			"warehouse": "Stores - _TC",
			"valuation_rate": 100,
			"stock_uom": "Nos"
		})
		self.assertTrue(stock_entry)
		sales_invoice = make_sales_invoice(delivery_note.name)
		sales_invoice.insert()
		sales_invoice.submit()
		self.assertEqual(sales_invoice.status, "Unpaid")
  
	def test_sales_order_update_stock_in_si_with_shipping_rule_TC_S_028(self):
		so = make_sales_order(cost_center='Main - _TC', selling_price_list='Standard Selling', qty=4, rate=5000, do_not_save=True)
		so.shipping_rule = "_Test Shipping Rule"
		so.save()
		so.submit()

		self.assertEqual(so.status, "To Deliver and Bill", "Sales Order not created")
		self.assertEqual(so.grand_total, so.total + so.total_taxes_and_charges)
  
		si = make_sales_invoice(so.name)
		si.update_stock = 1
		si.save()
		si.submit()

		self.assertEqual(si.status, "Unpaid", "Sales Invoice not created")
  
		qty_change = frappe.db.get_value('Stock Ledger Entry', {'item_code': '_Test Item', 'voucher_no': si.name, 'warehouse': '_Test Warehouse - _TC'}, 'actual_qty')
		self.assertEqual(qty_change, -4)
  
		voucher_params_si = {
			'voucher_type': 'Sales Invoice', 'voucher_no': si.name
		}
		gl_accounts_si = {
			'Sales - _TC': 'credit',
			'Debtors - _TC': 'debit',
			'_Test Account Shipping Charges - _TC': 'credit'
		}
		gl_entries_si = {
			account: frappe.db.get_value('GL Entry', {**voucher_params_si, 'account': account}, field)
			for account, field in gl_accounts_si.items()
		}
		self.assertEqual(gl_entries_si['Sales - _TC'], 20000)
		self.assertEqual(gl_entries_si['Debtors - _TC'], 20200)
		self.assertEqual(gl_entries_si['_Test Account Shipping Charges - _TC'], 200)
  
	def test_sales_order_update_stock_in_partial_si_with_shipping_rule_TC_S_029(self):
		so = make_sales_order(cost_center='Main - _TC', selling_price_list='Standard Selling', qty=4, rate=5000, do_not_save=True)
		so.shipping_rule = "_Test Shipping Rule"
		so.save()
		so.submit()

		self.assertEqual(so.status, "To Deliver and Bill", "Sales Order not created")
		self.assertEqual(so.grand_total, so.total + so.total_taxes_and_charges)
  
		si1 = make_sales_invoice(so.name)
		si1.get("items")[0].qty = 2
		si1.update_stock = 1
		si1.save()
		si1.submit()

		self.assertEqual(si1.status, "Unpaid", "Sales Invoice not created")
  
		qty_change1 = frappe.db.get_value('Stock Ledger Entry', {'item_code': '_Test Item', 'voucher_no': si1.name, 'warehouse': '_Test Warehouse - _TC'}, 'actual_qty')
		self.assertEqual(qty_change1, -2)
  
		voucher_params_si1 = {
			'voucher_type': 'Sales Invoice',
			'voucher_no': si1.name
		}
		gl_accounts_si1 = {
			'Sales - _TC': 'credit',
			'Debtors - _TC': 'debit',
			'_Test Account Shipping Charges - _TC': 'credit'
		}
		gl_entries_si1 = {
			account: frappe.db.get_value('GL Entry', {**voucher_params_si1, 'account': account}, field)
			for account, field in gl_accounts_si1.items()
		}
		self.assertEqual(gl_entries_si1['Sales - _TC'], 10000)
		self.assertEqual(gl_entries_si1['Debtors - _TC'], 10200)
		self.assertEqual(gl_entries_si1['_Test Account Shipping Charges - _TC'], 200)
  
		si2 = make_sales_invoice(so.name)
		si2.update_stock = 1
		si2.save()
		si2.submit()

		self.assertEqual(si2.status, "Unpaid", "Sales Invoice not created")
  
		qty_change2 = frappe.db.get_value('Stock Ledger Entry', {'item_code': '_Test Item', 'voucher_no': si2.name, 'warehouse': '_Test Warehouse - _TC'}, 'actual_qty')
		self.assertEqual(qty_change2, -2)
  
		voucher_params_si2 = {
			'voucher_type': 'Sales Invoice',
			'voucher_no': si2.name
		}
		gl_accounts_si2 = {
			'Sales - _TC': 'credit',
			'Debtors - _TC': 'debit',
			'_Test Account Shipping Charges - _TC': 'credit'
		}
		gl_entries_si2 = {
			account: frappe.db.get_value('GL Entry', {**voucher_params_si2, 'account': account}, field)
			for account, field in gl_accounts_si2.items()
		}
		self.assertEqual(gl_entries_si2['Sales - _TC'], 10000)
		self.assertEqual(gl_entries_si2['Debtors - _TC'], 10200)
		self.assertEqual(gl_entries_si2['_Test Account Shipping Charges - _TC'], 200)

	def test_sales_order_for_sales_return_TC_S_033(self):
		so = make_sales_order(cost_center='Main - _TC', selling_price_list='Standard Selling', qty=5, rate=3000, do_not_save=True)
		so.save()
		so.submit()
  
		self.assertEqual(so.status, "To Deliver and Bill", "Sales Order not created")
  
		dn = make_delivery_note(so.name)
		dn.save()
		dn.submit()

		self.assertEqual(dn.status, "To Bill", "Delivery Note not created")
  
		qty_change_dn = frappe.db.get_value('Stock Ledger Entry', {'item_code': '_Test Item', 'voucher_no': dn.name, 'warehouse': '_Test Warehouse - _TC'}, 'actual_qty')
		self.assertEqual(qty_change_dn, -5)
  
		from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_return
  
		sr = make_sales_return(dn.name)
		sr.save()
		sr.submit()
  
		self.assertEqual(sr.status, "To Bill", "Sales Return not created")
  
		qty_change_return = frappe.db.get_value('Stock Ledger Entry', {'item_code': '_Test Item', 'voucher_no': sr.name, 'warehouse': '_Test Warehouse - _TC'}, 'actual_qty')
		self.assertEqual(qty_change_return, 5)
  
	def test_sales_order_for_sales_return_via_si_TC_S_034(self):
		so = make_sales_order(cost_center='Main - _TC', selling_price_list='Standard Selling', qty=5, rate=3000, do_not_save=True)
		so.save()
		so.submit()
  
		self.assertEqual(so.status, "To Deliver and Bill", "Sales Order not created")
  
		dn = make_delivery_note(so.name)
		dn.save()
		dn.submit()

		self.assertEqual(dn.status, "To Bill", "Delivery Note not created")
  
		qty_change_dn = frappe.db.get_value('Stock Ledger Entry', {'item_code': '_Test Item', 'voucher_no': dn.name, 'warehouse': '_Test Warehouse - _TC'}, 'actual_qty')
		self.assertEqual(qty_change_dn, -5)
  
		from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_invoice
		si = make_sales_invoice(dn.name)
		si.save()
		si.submit()
  
		self.assertEqual(si.status, "Unpaid", "Sales Invoice not created")

		voucher_params_si = {
			'voucher_type': 'Sales Invoice', 'voucher_no': si.name
		}
		gl_accounts_si = {
			'Sales - _TC': 'credit', 'Debtors - _TC': 'debit'
		}
		gl_entries_si = {
			account: frappe.db.get_value('GL Entry', {**voucher_params_si, 'account': account}, field)
			for account, field in gl_accounts_si.items()
		}
		self.assertEqual(gl_entries_si['Sales - _TC'], 15000)
		self.assertEqual(gl_entries_si['Debtors - _TC'], 15000)
  
		from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_return
  
		sr = make_sales_return(dn.name)
		sr.save()
		sr.submit()
  
		self.assertEqual(sr.status, "To Bill", "Sales Return not created")
  
		qty_change_return = frappe.db.get_value('Stock Ledger Entry', {'item_code': '_Test Item', 'voucher_no': sr.name, 'warehouse': '_Test Warehouse - _TC'}, 'actual_qty')
		self.assertEqual(qty_change_return, 5)
  
		from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_sales_return as make_credit_note
  
		cn = make_credit_note(si.name)
		cn.save()
		cn.submit()
  
		self.assertEqual(cn.status, "Return", "Credit Note not created")
  
		voucher_params_cn = {
			'voucher_type': 'Sales Invoice', 'voucher_no': cn.name
		}
		gl_accounts_cn = {
			'Debtors - _TC': 'credit', 'Sales - _TC': 'debit'
		}
		gl_entries_cn = {
			account: frappe.db.get_value('GL Entry', {**voucher_params_cn, 'account': account}, field)
			for account, field in gl_accounts_cn.items()
		}
		self.assertEqual(gl_entries_cn['Debtors - _TC'], 15000)
		self.assertEqual(gl_entries_cn['Sales - _TC'], 15000)
  
	def test_sales_order_for_partial_return_TC_S_035(self):
		so = make_sales_order(cost_center='Main - _TC', selling_price_list='Standard Selling', qty=5, rate=3000, do_not_save=True)
		so.save()
		so.submit()
  
		self.assertEqual(so.status, "To Deliver and Bill", "Sales Order not created")
  
		dn = make_delivery_note(so.name)
		dn.save()
		dn.submit()

		self.assertEqual(dn.status, "To Bill", "Delivery Note not created")
  
		qty_change_dn = frappe.db.get_value('Stock Ledger Entry', {'item_code': '_Test Item', 'voucher_no': dn.name, 'warehouse': '_Test Warehouse - _TC'}, 'actual_qty')
		self.assertEqual(qty_change_dn, -5)
  
		from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_return
  
		sr = make_sales_return(dn.name)
		sr.items[0].qty = -2
		sr.save()
		sr.submit()
  
		self.assertEqual(sr.status, "To Bill", "Sales Return not created")
  
		qty_change_return = frappe.db.get_value('Stock Ledger Entry', {'item_code': '_Test Item', 'voucher_no': sr.name, 'warehouse': '_Test Warehouse - _TC'}, 'actual_qty')
		self.assertEqual(qty_change_return, 2)
  
		from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_invoice
		si = make_sales_invoice(dn.name)
		si.save()
		si.submit()
  
		self.assertEqual(si.status, "Unpaid", "Sales Invoice not created")

		voucher_params_si = {
			'voucher_type': 'Sales Invoice', 'voucher_no': si.name
		}
		gl_accounts_si = {
			'Sales - _TC': 'credit', 'Debtors - _TC': 'debit'
		}
		gl_entries_si = {
			account: frappe.db.get_value('GL Entry', {**voucher_params_si, 'account': account}, field)
			for account, field in gl_accounts_si.items()
		}
		self.assertEqual(gl_entries_si['Sales - _TC'], 9000)
		self.assertEqual(gl_entries_si['Debtors - _TC'], 9000)
  
	def test_sales_order_for_sales_return_via_payment_entry_TC_S_036(self):
		so = make_sales_order(cost_center='Main - _TC', selling_price_list='Standard Selling', qty=5, rate=3000, do_not_save=True)
		so.save()
		so.submit()
  
		self.assertEqual(so.status, "To Deliver and Bill", "Sales Order not created")
  
		dn = make_delivery_note(so.name)
		dn.save()
		dn.submit()

		self.assertEqual(dn.status, "To Bill", "Delivery Note not created")
  
		qty_change_dn = frappe.db.get_value('Stock Ledger Entry', {'item_code': '_Test Item', 'voucher_no': dn.name, 'warehouse': '_Test Warehouse - _TC'}, 'actual_qty')
		self.assertEqual(qty_change_dn, -5)
  
		from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_invoice
		si = make_sales_invoice(dn.name)
		si.save()
		si.submit()
  
		self.assertEqual(si.status, "Unpaid", "Sales Invoice not created")

		voucher_params_si = {
			'voucher_type': 'Sales Invoice', 'voucher_no': si.name
		}
		gl_accounts_si = {
			'Sales - _TC': 'credit', 'Debtors - _TC': 'debit'
		}
		gl_entries_si = {
			account: frappe.db.get_value('GL Entry', {**voucher_params_si, 'account': account}, field)
			for account, field in gl_accounts_si.items()
		}
		self.assertEqual(gl_entries_si['Sales - _TC'], 15000)
		self.assertEqual(gl_entries_si['Debtors - _TC'], 15000)
  
		from erpnext.accounts.doctype.payment_entry.test_payment_entry import create_payment_entry
		pe = create_payment_entry(
				payment_type="Receive",
				party_type="Customer",
				party="_Test Customer",
				paid_from="Debtors - _TC",
				paid_to="Cash - _TC",
				paid_amount=15000,
			)
		reference = pe.append('references')  
		reference.references_doctype = "Sales Invoice"
		reference.references_name = si.name
		reference.total_amount = 15000
		reference.account = "Debtors - _TC"
		pe.save()
		pe.submit()
  
		pe_acc_credit = frappe.db.get_value('GL Entry', {'voucher_type': 'Payment Entry', 'voucher_no': pe.name, 'account': 'Debtors - _TC'}, 'credit')
		self.assertEqual(pe_acc_credit, 15000)

		pe_acc_debit = frappe.db.get_value('GL Entry', {'voucher_type': 'Payment Entry', 'voucher_no': pe.name, 'account': 'Cash - _TC'}, 'debit')
		self.assertEqual(pe_acc_debit, 15000)
  
		from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_return
		sr = make_sales_return(dn.name)
		sr.save()
		sr.submit()
  
		self.assertEqual(sr.status, "To Bill", "Sales Return not created")
  
		qty_change_return = frappe.db.get_value('Stock Ledger Entry', {'item_code': '_Test Item', 'voucher_no': sr.name, 'warehouse': '_Test Warehouse - _TC'}, 'actual_qty')
		self.assertEqual(qty_change_return, 5)
  
		from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_sales_return as make_credit_note
		cn = make_credit_note(si.name)
		cn.save()
		cn.submit()
  
		self.assertEqual(cn.status, "Return", "Credit Note not created")
  
		voucher_params_cn = {
			'voucher_type': 'Sales Invoice', 'voucher_no': cn.name
		}
		gl_accounts_cn = {
			'Debtors - _TC': 'credit', 'Sales - _TC': 'debit'
		}
		gl_entries_cn = {
			account: frappe.db.get_value('GL Entry', {**voucher_params_cn, 'account': account}, field)
			for account, field in gl_accounts_cn.items()
		}
		self.assertEqual(gl_entries_cn['Debtors - _TC'], 15000)
		self.assertEqual(gl_entries_cn['Sales - _TC'], 15000)
  
	def test_sales_order_for_partial_sales_return_via_payment_entry_TC_S_037(self):
		so = make_sales_order(cost_center='Main - _TC', selling_price_list='Standard Selling', qty=5, rate=3000, do_not_save=True)
		so.save()
		so.submit()

		self.assertEqual(so.status, "To Deliver and Bill", "Sales Order not created")

		dn = make_delivery_note(so.name)
		dn.save()
		dn.submit()

		self.assertEqual(dn.status, "To Bill", "Delivery Note not created")

		qty_change_dn = frappe.db.get_value('Stock Ledger Entry', {
			'item_code': '_Test Item',
			'voucher_no': dn.name,
			'warehouse': '_Test Warehouse - _TC'
		}, 'actual_qty')
		self.assertEqual(qty_change_dn, -5)

		from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_invoice
		si = make_sales_invoice(dn.name)
		si.save()
		si.submit()

		self.assertEqual(si.status, "Unpaid", "Sales Invoice not created")

		def validate_gl_entries(voucher_type, voucher_no, accounts):
			for account, field, expected_value in accounts:
				actual_value = frappe.db.get_value('GL Entry', {
					'voucher_type': voucher_type,
					'voucher_no': voucher_no,
					'account': account
				}, field)
				self.assertEqual(actual_value, expected_value)

		validate_gl_entries('Sales Invoice', si.name, [
			('Sales - _TC', 'credit', 15000),
			('Debtors - _TC', 'debit', 15000)
		])

		from erpnext.accounts.doctype.payment_entry.test_payment_entry import create_payment_entry
		pe = create_payment_entry(
			payment_type="Receive",
			party_type="Customer",
			party="_Test Customer",
			paid_from="Debtors - _TC",
			paid_to="Cash - _TC",
			paid_amount=15000,
		)
		reference = pe.append('references')
		reference.reference_doctype = "Sales Invoice"
		reference.reference_name = si.name
		reference.total_amount = 15000
		reference.account = "Debtors - _TC"
		pe.save()
		pe.submit()

		validate_gl_entries('Payment Entry', pe.name, [
			('Debtors - _TC', 'credit', 15000),
			('Cash - _TC', 'debit', 15000)
		])

		from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_return
		sr = make_sales_return(dn.name)
		sr.items[0].qty = -2
		sr.save()
		sr.submit()

		self.assertEqual(sr.status, "To Bill", "Sales Return not created")

		qty_change_return = frappe.db.get_value('Stock Ledger Entry', {
			'item_code': '_Test Item',
			'voucher_no': sr.name,
			'warehouse': '_Test Warehouse - _TC'
		}, 'actual_qty')
		self.assertEqual(qty_change_return, 2)

		from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_sales_return as make_credit_note
		cn = make_credit_note(si.name)
		cn.save()
		cn.submit()

		self.assertEqual(cn.status, "Return", "Credit Note not created")

		validate_gl_entries('Sales Invoice', cn.name, [
			('Debtors - _TC', 'credit', 15000),
			('Sales - _TC', 'debit', 15000)
		])

		so.reload()
		self.assertEqual(so.status, "To Deliver", "Sales Order not updated")
 
	def test_sales_order_create_si_via_pe_dn_with_gst_TC_S_042(self):
		company = get_gst_details("Company", {"name": "_Test Indian Registered Company"})[0]
		customer = get_gst_details("Customer", {"name": "_Test Registered Customer"})[0]
		company_add = get_gst_details("Address", {"name": "_Test Indian Registered Company-Billing"})[0]
		customer_add = get_gst_details("Address", {"name": "_Test Registered Customer-Billing"})[0]

		if not (is_registered_regular(company) and is_registered_regular(customer) and
				is_registered_regular(company_add) and is_registered_regular(customer_add)):
			self.fail("GST details are not properly configured")

		so = make_sales_order(
			company="_Test Indian Registered Company",
			customer="_Test Registered Customer",
			warehouse="Stores - _TIRC",
			cost_center="Main - _TIRC",
			selling_price_list="Standard Selling",
			item_code="_Test Item",
			qty=1,
			rate=5000,
			do_not_save=True
		)
		so.tax_category = "In-State"
		so.taxes_and_charges = "Output GST In-state - _TIRC"
		so.customer_address = customer_add.get("name")
		so.billing_address_gstin = customer_add.get("gstin")
		so.company_address = company_add.get("name")
		so.company_gstin = company_add.get("gstin")
		so.save()
		so.submit()

		self.assertEqual(so.status, "To Deliver and Bill", "Sales Order not created")
		self.assertEqual(so.grand_total, so.total + so.total_taxes_and_charges)

		from erpnext.accounts.doctype.payment_entry.test_payment_entry import create_payment_entry

		pe = create_payment_entry(
			company="_Test Indian Registered Company",
			payment_type="Receive",
			party_type="Customer",
			party="_Test Registered Customer",
			paid_from="Debtors - _TIRC",
			paid_to="Cash - _TIRC",
			paid_amount=so.grand_total,
		)
		pe.append("references", {
			"reference_doctype": "Sales Order",
			"reference_name": so.name,
			"total_amount": so.grand_total,
			"account": "Debtors - _TIRC"
		})
		pe.save()
		pe.submit()

		self.assertEqual(
			frappe.db.get_value("GL Entry", {"voucher_type": "Payment Entry", "voucher_no": pe.name, "account": "Debtors - _TIRC"}, "credit"),
			so.grand_total
		)
		self.assertEqual(
			frappe.db.get_value("GL Entry", {"voucher_type": "Payment Entry", "voucher_no": pe.name, "account": "Cash - _TIRC"}, "debit"),
			so.grand_total
		)

		dn = make_delivery_note(so.name)
		dn.submit()

		stock_entry = frappe.get_all("Stock Ledger Entry", {
			"voucher_type": "Delivery Note",
			"voucher_no": dn.name,
			"warehouse": "Stores - _TIRC",
			"item_code": "_Test Item"
		}, ["valuation_rate", "actual_qty"])[0]

		self.assertEqual(stock_entry.get("actual_qty"), -1)
		self.assertEqual(
			frappe.db.get_value("GL Entry", {"voucher_type": "Delivery Note", "voucher_no": dn.name, "account": "Stock In Hand - _TIRC"}, "credit"),
			stock_entry.get("valuation_rate")
		)
		self.assertEqual(
			frappe.db.get_value("GL Entry", {"voucher_type": "Delivery Note", "voucher_no": dn.name, "account": "Cost of Goods Sold - _TIRC"}, "debit"),
			stock_entry.get("valuation_rate")
		)

		from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_invoice

		si = make_sales_invoice(dn.name)
		si.allocate_advances_automatically = 1
		si.save()
		si.submit()

		self.assertEqual(si.status, "Unpaid")
		self.assertEqual(
			frappe.db.get_value("GL Entry", {"voucher_type": "Sales Invoice", "voucher_no": si.name, "account": "Sales - _TIRC"}, "credit"),
			5000
		)
		self.assertEqual(
			frappe.db.get_value("GL Entry", {"voucher_type": "Sales Invoice", "voucher_no": si.name, "account": "Debtors - _TIRC"}, "debit"),
			5900
		)
		self.assertEqual(
			frappe.db.get_value("GL Entry", {"voucher_type": "Sales Invoice", "voucher_no": si.name, "account": "Output Tax SGST - _TIRC"}, "credit"),
			450
		)
		self.assertEqual(
			frappe.db.get_value("GL Entry", {"voucher_type": "Sales Invoice", "voucher_no": si.name, "account": "Output Tax CGST - _TIRC"}, "credit"),
			450
		)
 
	def test_sales_order_create_si_via_partial_pe_dn_with_gst_TC_S_043(self):
		company = get_gst_details("Company", {"name": "_Test Indian Registered Company"})
		customer = get_gst_details("Customer", {"name": "_Test Registered Customer"})
		company_add = get_gst_details("Address", {"name": "_Test Indian Registered Company-Billing"})
		customer_add = get_gst_details("Address", {"name": "_Test Registered Customer-Billing"})

		if not (is_registered_regular(company[0]) and is_registered_regular(customer[0]) and 
				is_registered_regular(company_add[0]) and is_registered_regular(customer_add[0])):
			self.fail("GST details are not properly configured")

		so = make_sales_order(
			company='_Test Indian Registered Company',
			customer='_Test Registered Customer',
			warehouse='Stores - _TIRC',
			cost_center='Main - _TIRC',
			selling_price_list='Standard Selling',
			item_code='_Test Item',
			qty=1,
			rate=5000,
			do_not_save=True
		)
		so.tax_category = 'In-State'
		so.taxes_and_charges = 'Output GST In-state - _TIRC'
		so.customer_address = customer_add[0].get("name")
		so.billing_address_gstin = customer_add[0].get("gstin")
		so.company_address = company_add[0].get("name")
		so.company_gstin = company_add[0].get("gstin")
		so.save()
		so.submit()

		self.assertEqual(so.status, "To Deliver and Bill", "Sales Order not created")
		self.assertEqual(so.grand_total, so.total + so.total_taxes_and_charges)
  
		create_registered_bank_account()
  
		from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
  
		pe = get_payment_entry(dt="Sales Order",dn=so.name)
		pe.reference_no = "1"
		pe.reference_date = nowdate()
		pe.paid_amount= 2000
		for i in pe.references:
			i.allocated_amount = 2000
		pe.save()
		pe.submit()
  
		self.assertEqual(pe.status, 'Submitted')
		self.assertEqual(frappe.db.get_value('GL Entry', {'voucher_no': pe.name, 'account': 'Debtors - _TIRC'}, 'credit'), 2000)
		self.assertEqual(frappe.db.get_value('GL Entry', {'voucher_no': pe.name, 'account': '_Test Registered Bank Account - _TIRC'}, 'debit'), 2000)

		dn = make_delivery_note(so.name)
		dn.submit()

		stock_entry = frappe.get_all('Stock Ledger Entry', {
			'voucher_no': dn.name, 
			'warehouse': 'Stores - _TIRC', 
			'item_code': '_Test Item'
		}, ['valuation_rate', 'actual_qty'])[0]
		self.assertEqual(stock_entry.get("actual_qty"), -1)

		dn_acc_value = stock_entry.get("valuation_rate")
		self.assertEqual(frappe.db.get_value('GL Entry', {'voucher_no': dn.name, 'account': 'Stock In Hand - _TIRC'}, 'credit'), dn_acc_value)
		self.assertEqual(frappe.db.get_value('GL Entry', {'voucher_no': dn.name, 'account': 'Cost of Goods Sold - _TIRC'}, 'debit'), dn_acc_value)

		from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_invoice

		si = make_sales_invoice(dn.name)
		si.allocate_advances_automatically = 1
		si.save()
		si.submit()

		self.assertEqual(si.status, 'Unpaid')

		self.assertEqual(frappe.db.get_value('GL Entry', {'voucher_no': si.name, 'account': 'Sales - _TIRC'}, 'credit'), 5000)
		self.assertEqual(frappe.db.get_value('GL Entry', {'voucher_no': si.name, 'account': 'Debtors - _TIRC'}, 'debit'), 5900)
		self.assertEqual(frappe.db.get_value('GL Entry', {'voucher_no': si.name, 'account': 'Output Tax SGST - _TIRC'}, 'credit'), 450)
		self.assertEqual(frappe.db.get_value('GL Entry', {'voucher_no': si.name, 'account': 'Output Tax CGST - _TIRC'}, 'credit'), 450)

		pe2 = get_payment_entry(dt="Sales Invoice",dn=si.name)
		pe2.reference_no = "1"
		pe2.reference_date = nowdate()
		pe2.save()
		pe2.submit()
  
		self.assertEqual(pe2.status, 'Submitted')
		self.assertEqual(frappe.db.get_value('GL Entry', {'voucher_no': pe2.name, 'account': 'Debtors - _TIRC'}, 'credit'), 3900)
		self.assertEqual(frappe.db.get_value('GL Entry', {'voucher_no': pe2.name, 'account': '_Test Registered Bank Account - _TIRC'}, 'debit'), 3900)

		si.reload()
		self.assertEqual(si.outstanding_amount, 0)

 
	def test_sales_order_with_full_advance_payment_and_shipping_rule_TC_S_044(self):
		so = make_sales_order(
			cost_center='Main - _TC', 
			selling_price_list='Standard Selling', 
			qty=1, 
			rate=5000, 
			do_not_save=True
		)
		so.shipping_rule = "_Test Shipping Rule"
		so.save()
		so.submit()

		self.assertEqual(so.status, "To Deliver and Bill", "Sales Order not created")
		self.assertEqual(so.grand_total, so.total + so.total_taxes_and_charges)

		from erpnext.accounts.doctype.payment_entry.test_payment_entry import create_payment_entry
		pe = create_payment_entry(
			payment_type="Receive",
			party_type="Customer",
			party="_Test Customer",
			paid_from="Debtors - _TC",
			paid_to="Cash - _TC",
			paid_amount=so.grand_total,
		)
		pe.append('references', {
			"reference_doctype": "Sales Order",
			"reference_name": so.name,
			"total_amount": so.grand_total,
			"account": "Debtors - _TC",
		})
		pe.save()
		pe.submit()

		self.assertEqual(
			frappe.db.get_value('GL Entry', {
				'voucher_type': 'Payment Entry',
				'voucher_no': pe.name,
				'account': 'Debtors - _TC'
			}, 'credit'),
			so.grand_total
		)
		self.assertEqual(
			frappe.db.get_value('GL Entry', {
				'voucher_type': 'Payment Entry',
				'voucher_no': pe.name,
				'account': 'Cash - _TC'
			}, 'debit'),
			so.grand_total
		)

		dn = make_delivery_note(so.name)
		dn.submit()

		stock_ledger_entry = frappe.get_all(
			'Stock Ledger Entry', 
			{'voucher_type': 'Delivery Note', 'voucher_no': dn.name, 'warehouse': '_Test Warehouse - _TC', 'item_code': '_Test Item'}, 
			['valuation_rate', 'actual_qty']
		)
		self.assertEqual(stock_ledger_entry[0].get("actual_qty"), -1)

		from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_invoice

		si = make_sales_invoice(dn.name)
		si.allocate_advances_automatically = 1
		si.save()
		si.submit()

		self.assertEqual(si.status, 'Paid')

		self.assertEqual(
			frappe.db.get_value('GL Entry', {
				'voucher_type': 'Sales Invoice',
				'voucher_no': si.name,
				'account': 'Sales - _TC'
			}, 'credit'),
			5000
		)
		self.assertEqual(
			frappe.db.get_value('GL Entry', {
				'voucher_type': 'Sales Invoice',
				'voucher_no': si.name,
				'account': 'Debtors - _TC'
			}, 'debit'),
			5200
		)
		self.assertEqual(
			frappe.db.get_value('GL Entry', {
				'voucher_type': 'Sales Invoice',
				'voucher_no': si.name,
				'account': '_Test Account Shipping Charges - _TC'
			}, 'credit'),
			200
		)
  
	def test_sales_order_with_partial_advance_payment_and_shipping_rule_TC_S_045(self):
		so = make_sales_order(
			cost_center='Main - _TC', 
			selling_price_list='Standard Selling', 
			qty=1, 
			rate=5000, 
			do_not_save=True
		)
		so.shipping_rule = "_Test Shipping Rule"
		so.save()
		so.submit()

		self.assertEqual(so.status, "To Deliver and Bill", "Sales Order not created")
		self.assertEqual(so.grand_total, so.total + so.total_taxes_and_charges)
  
		create_registered_bank_account()

		from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
  
		pe = get_payment_entry(dt="Sales Order",dn=so.name)
		pe.reference_no = "1"
		pe.reference_date = nowdate()
		pe.paid_amount= 2000
		for i in pe.references:
			i.allocated_amount = 2000
		pe.save()
		pe.submit()
  
		self.assertEqual(pe.status, 'Submitted')
		self.assertEqual(frappe.db.get_value('GL Entry', {'voucher_no': pe.name, 'account': 'Debtors - _TC'}, 'credit'), 2000)
		self.assertEqual(frappe.db.get_value('GL Entry', {'voucher_no': pe.name, 'account': 'Cash - _TC'}, 'debit'), 2000)

		dn = make_delivery_note(so.name)
		dn.submit()

		stock_ledger_entry = frappe.get_all(
			'Stock Ledger Entry', 
			{'voucher_type': 'Delivery Note', 'voucher_no': dn.name, 'warehouse': '_Test Warehouse - _TC', 'item_code': '_Test Item'}, 
			['valuation_rate', 'actual_qty']
		)
		self.assertEqual(stock_ledger_entry[0].get("actual_qty"), -1)

		from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_invoice

		si = make_sales_invoice(dn.name)
		si.allocate_advances_automatically = 1
		si.save()
		si.submit()

		self.assertEqual(si.status, 'Unpaid')

		self.assertEqual(frappe.db.get_value('GL Entry', {'voucher_type': 'Sales Invoice','voucher_no': si.name,'account': 'Sales - _TC'}, 'credit'),
			5000
		)
		self.assertEqual(frappe.db.get_value('GL Entry', {'voucher_type': 'Sales Invoice','voucher_no': si.name,'account': 'Debtors - _TC'}, 'debit'),
			5200
		)
		self.assertEqual(frappe.db.get_value('GL Entry', {'voucher_type': 'Sales Invoice','voucher_no': si.name,'account': '_Test Account Shipping Charges - _TC'}, 'credit'),
			200
		)
  
		pe2 = get_payment_entry(dt="Sales Invoice",dn=si.name)
		pe2.reference_no = "1"
		pe2.reference_date = nowdate()
		pe2.save()
		pe2.submit()
  
		self.assertEqual(pe2.status, 'Submitted')
		self.assertEqual(frappe.db.get_value('GL Entry', {'voucher_no': pe2.name, 'account': 'Debtors - _TC'}, 'credit'), 3200)
		self.assertEqual(frappe.db.get_value('GL Entry', {'voucher_no': pe2.name, 'account': 'Cash - _TC'}, 'debit'), 3200)

		si.reload()
		self.assertEqual(si.outstanding_amount, 0)
  
	def test_sales_order_create_si_via_pe_dn_with_pricing_rule_TC_S_046(self):
		make_item_price()
		make_pricing_rule()
  
		so = self.create_and_submit_sales_order(qty=10)
  
		from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
  
		pe = get_payment_entry(dt="Sales Order",dn=so.name)
		pe.save()
		pe.submit()
  
		self.assertEqual(pe.status, 'Submitted')
		self.assertEqual(frappe.db.get_value('GL Entry', {'voucher_no': pe.name, 'account': 'Debtors - _TC'}, 'credit'), 900)
		self.assertEqual(frappe.db.get_value('GL Entry', {'voucher_no': pe.name, 'account': 'Cash - _TC'}, 'debit'), 900)
  
		dn = make_delivery_note(so.name)
		dn.submit()

		self.assertEqual(dn.status, "To Bill", "Delivery Note not created")
		stock_ledger_entry = frappe.get_all(
			'Stock Ledger Entry', 
			{'voucher_type': 'Delivery Note', 'voucher_no': dn.name, 'warehouse': '_Test Warehouse - _TC', 'item_code': '_Test Item'}, 
			['valuation_rate', 'actual_qty']
		)
		self.assertEqual(stock_ledger_entry[0].get("actual_qty"), -10)

		si = self.create_and_submit_sales_invoice(dn.name,advances_automatically= 1,expected_amount=900)
		si.reload()
		self.assertEqual(si.status, "Paid")
  
	def test_sales_order_create_si_via_partial_pe_with_pricing_rule_TC_S_047(self):
		make_item_price()
		make_pricing_rule()
  
		so = self.create_and_submit_sales_order(qty=10)
  
		from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
  
		pe = get_payment_entry(dt="Sales Order",dn=so.name)
		pe.paid_amount= 400
		for i in pe.references:
			i.allocated_amount = 400
		pe.save()
		pe.submit()
  
		self.assertEqual(pe.status, 'Submitted')
		self.assertEqual(frappe.db.get_value('GL Entry', {'voucher_no': pe.name, 'account': 'Debtors - _TC'}, 'credit'), 400)
		self.assertEqual(frappe.db.get_value('GL Entry', {'voucher_no': pe.name, 'account': 'Cash - _TC'}, 'debit'), 400)
  
		dn = make_delivery_note(so.name)
		dn.submit()

		self.assertEqual(dn.status, "To Bill", "Delivery Note not created")
		stock_ledger_entry = frappe.get_all(
			'Stock Ledger Entry', 
			{'voucher_type': 'Delivery Note', 'voucher_no': dn.name, 'warehouse': '_Test Warehouse - _TC', 'item_code': '_Test Item'}, 
			['valuation_rate', 'actual_qty']
		)
		self.assertEqual(stock_ledger_entry[0].get("actual_qty"), -10)

		si = self.create_and_submit_sales_invoice(dn.name,advances_automatically= 1,expected_amount=900)
		si.reload()
		self.assertEqual(si.status, "Partly Paid")
  
		pe=get_payment_entry(dt="Sales Invoice",dn=si.name)
		pe.save()
		pe.submit()

		si.reload()
		self.assertEqual(si.status, "Paid")
  
	def test_sales_order_creating_credit_note_after_SR_TC_S_048(self):
		so = self.create_and_submit_sales_order(qty=5, rate=3000)
  
		from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
  
		pe = get_payment_entry(dt="Sales Order",dn=so.name)
		pe.save()
		pe.submit()
  
		self.assertEqual(pe.status, 'Submitted')
		self.assertEqual(frappe.db.get_value('GL Entry', {'voucher_no': pe.name, 'account': 'Debtors - _TC'}, 'credit'), 15000)
		self.assertEqual(frappe.db.get_value('GL Entry', {'voucher_no': pe.name, 'account': 'Cash - _TC'}, 'debit'), 15000)
  
		dn = self.create_and_validate_delivery_note(so.name, -5)

		si = self.create_and_submit_sales_invoice(dn.name,advances_automatically= 1,expected_amount=15000)
		si.reload()
		self.assertEqual(si.status, "Paid")
  
		from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_return
		sr = make_sales_return(dn.name)
		sr.save()
		sr.submit()

		self.assertEqual(sr.status, "To Bill", "Sales Return not created")

		qty_change_return = frappe.db.get_value('Stock Ledger Entry', {
			'item_code': '_Test Item',
			'voucher_no': sr.name,
			'warehouse': '_Test Warehouse - _TC'
		}, 'actual_qty')
		self.assertEqual(qty_change_return, 5)
  
		from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_sales_return as make_credit_note
		cn = make_credit_note(si.name)
		cn.advances.clear()
		cn.save()
		cn.submit()
  
		self.assertEqual(cn.status, "Return", "Credit Note not created")
  
		voucher_params_cn = {'voucher_type': 'Sales Invoice', 'voucher_no': cn.name}
		gl_accounts_cn = {'Debtors - _TC': 'credit', 'Sales - _TC': 'debit'}
		gl_entries_cn = {
      		account: frappe.db.get_value('GL Entry', {**voucher_params_cn, 'account': account}, field)
			for account, field in gl_accounts_cn.items()
		}
		self.assertEqual(gl_entries_cn['Debtors - _TC'], 15000)
		self.assertEqual(gl_entries_cn['Sales - _TC'], 15000)
 
	def test_sales_order_creating_full_si_for_service_item_SI_TC_S_050(self):
		make_service_item()
  
		so = make_sales_order(cost_center='Main - _TC', selling_price_list='Standard Selling', item_code='Consultancy', qty=1, rate=5000)
		so.save()
		so.submit()

		self.assertEqual(so.status, "To Deliver and Bill", "Sales Order not created")
  
		from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
  
		pe = get_payment_entry(dt="Sales Order",dn=so.name)
		pe.save()
		pe.submit()
  
		self.assertEqual(pe.status, 'Submitted')
		self.assertEqual(frappe.db.get_value('GL Entry', {'voucher_no': pe.name, 'account': 'Debtors - _TC'}, 'credit'), 5000)
		self.assertEqual(frappe.db.get_value('GL Entry', {'voucher_no': pe.name, 'account': 'Cash - _TC'}, 'debit'), 5000)
  
		si = make_sales_invoice(so.name)
		si.allocate_advances_automatically= 1
		si.only_include_allocated_payments = 1
		si.save()
		si.submit()
		si.reload()

		self.assertEqual(si.status, "Paid", "Sales Invoice not created")
		self.assertEqual(frappe.db.get_value('GL Entry', {'voucher_no': si.name, 'account': 'Sales - _TC'}, 'credit'), 5000)
		self.assertEqual(frappe.db.get_value('GL Entry', {'voucher_no': si.name, 'account': 'Debtors - _TC'}, 'debit'), 5000)
 
	def create_and_submit_sales_order(self, qty=None, rate=None):
		sales_order = make_sales_order(cost_center='Main - _TC', selling_price_list='Standard Selling', do_not_save=True)
		sales_order.delivery_date = nowdate()
		if qty and rate:
			for item in sales_order.items:
				item.qty = qty
				item.rate = rate
			sales_order.save()
		else:
			for item in sales_order.items:
				item.qty = qty
			sales_order.save()
		sales_order.submit()
		self.assertEqual(sales_order.status, "To Deliver and Bill")
		return sales_order
 
	def create_and_submit_sales_invoice(self, delivery_note_name, qty=None, expected_amount=None,advances_automatically=None):
		from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_invoice
		sales_invoice = make_sales_invoice(delivery_note_name)
		sales_invoice.insert()
		if qty:
			for item in sales_invoice.items:
				item.qty = qty

		if advances_automatically:
			sales_invoice.allocate_advances_automatically= 1
			sales_invoice.only_include_allocated_payments = 1
		sales_invoice.save()
		sales_invoice.submit()
		if expected_amount:
			self.validate_gl_entries(sales_invoice.name, expected_amount)
		return sales_invoice

	def validate_gl_entries(self, voucher_no, amount):
		debtor_account = frappe.db.get_value("Company", "_Test Company", "default_receivable_account")
		sales_account = frappe.db.get_value("Company", "_Test Company", "default_income_account")
		gl_entries = frappe.get_all("GL Entry", filters={"voucher_no": voucher_no}, fields=["account", "debit", "credit"])

		gl_debits = {entry.account: entry.debit for entry in gl_entries}
		gl_credits = {entry.account: entry.credit for entry in gl_entries}

		self.assertAlmostEqual(gl_debits[debtor_account], amount)
		self.assertAlmostEqual(gl_credits[sales_account], amount)
  
	def create_and_validate_delivery_note(self, sales_order_name, expected_amount):
		delivery_note = make_delivery_note(sales_order_name)
		delivery_note.submit()

		self.assertEqual(delivery_note.status, "To Bill", "Delivery Note not created")
		stock_ledger_entry = frappe.get_all(
			'Stock Ledger Entry', 
			{'voucher_type': 'Delivery Note', 'voucher_no': delivery_note.name, 'warehouse': '_Test Warehouse - _TC', 'item_code': '_Test Item'}, 
			['valuation_rate', 'actual_qty']
		)
		self.assertEqual(stock_ledger_entry[0].get("actual_qty"), expected_amount)
  
		return delivery_note
		

def get_gst_details(doctype, filters):
	return frappe.get_all(doctype, filters, ["gstin", "gst_category", "name"])

def is_registered_regular(details):
			return details.get("gst_category") == "Registered Regular" and details.get("gstin")

def create_registered_bank_account():
	if not frappe.db.exists('Account', {'name': '_Test Registered Bank Account - _TIRC'}):
		acc_doc = frappe.new_doc("Account")
		acc_data = {
			"company": "_Test Indian Registered Company",
			"parent_account":"Bank Accounts - _TIRC"
		}
		acc_doc.update(acc_data)
		acc_doc.save()
		return acc_doc

def automatically_fetch_payment_terms(enable=1):
	accounts_settings = frappe.get_doc("Accounts Settings")
	accounts_settings.automatically_fetch_payment_terms = enable
	accounts_settings.save()


def compare_payment_schedules(doc, doc1, doc2):
	for index, schedule in enumerate(doc1.get("payment_schedule")):
		doc.assertEqual(schedule.payment_term, doc2.payment_schedule[index].payment_term)
		doc.assertEqual(getdate(schedule.due_date), doc2.payment_schedule[index].due_date)
		doc.assertEqual(schedule.invoice_portion, doc2.payment_schedule[index].invoice_portion)
		doc.assertEqual(schedule.payment_amount, doc2.payment_schedule[index].payment_amount)


def make_sales_order(**args):
	so = frappe.new_doc("Sales Order")
	args = frappe._dict(args)
	if args.transaction_date:
		so.transaction_date = args.transaction_date

	so.set_warehouse = ""  # no need to test set_warehouse permission since it only affects the client
	so.company = args.company or "_Test Company"
	so.customer = args.customer or "_Test Customer"
	so.currency = args.currency or "INR"
	so.po_no = args.po_no or ""
	if args.selling_price_list:
		so.selling_price_list = args.selling_price_list
	if args.cost_center:
		so.cost_center = args.cost_center

	if "warehouse" not in args:
		args.warehouse = "_Test Warehouse - _TC"

	if args.item_list:
		for item in args.item_list:
			so.append("items", item)

	else:
		so.append(
			"items",
			{
				"item_code": args.item or args.item_code or "_Test Item",
				"warehouse": args.warehouse,
				"qty": args.qty or 10,
				"uom": args.uom or None,
				"price_list_rate": args.price_list_rate or None,
				"discount_percentage": args.discount_percentage or None,
				"rate": args.rate or (None if args.price_list_rate else 100),
				"against_blanket_order": args.against_blanket_order,
			},
		)

	so.delivery_date = add_days(so.transaction_date, 10)

	if not args.do_not_save:
		so.insert()
		if not args.do_not_submit:
			so.submit()
		else:
			so.payment_schedule = []
	else:
		so.payment_schedule = []

	return so

def make_service_item():
	if not frappe.db.exists('Item', {'item_code': 'Consultancy'}):
		si_doc = frappe.new_doc("Item")
		item_price_data = {
			"item_code": 'Consultancy',
			"stock_uom": 'Hrs',
			"in_stock_item": 0,
			"item_group": "Services",
			"gst_hsn_code": "01011020",
			"description": "Consultancy",
			"is_purchase_item": 1,
			"grant_commission": 1,
			"is_sales_item": 1
		}
		si_doc.update(item_price_data)
		si_doc.save()
		return si_doc

def make_item_price():
    if not frappe.db.exists('Item Price', {'item_code': '_Test Item'}):
        ip_doc = frappe.new_doc("Item Price")
        item_price_data = {
            "item_code": '_Test Item',
            "uom": '_Test UOM',
            "price_list": 'Standard Selling',
            "selling": 1,
            "price_list_rate": 100
        }
        ip_doc.update(item_price_data)
        ip_doc.save()
        return ip_doc

def make_pricing_rule():
    if not frappe.db.exists('Pricing Rule', {'title': 'Test Offer'}):
        pricing_rule_doc = frappe.new_doc('Pricing Rule')
        pricing_rule_data = {
            "title": 'Test Offer',
            "apply_on": 'Item Code',
            "price_or_product_discount": 'Price',
            "selling": 1,
            "min_qty": 10,
            "company": '_Test Company',
            "margin_type": 'Percentage',
            "discount_percentage": 10,
            "for_price_list": 'Standard Selling',
			"items":[ {"item_code": "_Test Item", "uom": '_Test UOM'}]
        }
        
        pricing_rule_doc.update(pricing_rule_data)
        pricing_rule_doc.save()
        return pricing_rule_doc



def create_dn_against_so(so, delivered_qty=0, do_not_submit=False):
	frappe.db.set_single_value("Stock Settings", "allow_negative_stock", 1)

	dn = make_delivery_note(so)
	dn.get("items")[0].qty = delivered_qty or 5
	dn.insert()
	if not do_not_submit:
		dn.submit()
	return dn


def get_reserved_qty(item_code="_Test Item", warehouse="_Test Warehouse - _TC"):
	return flt(frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": warehouse}, "reserved_qty"))


test_dependencies = ["Currency Exchange"]


def make_sales_order_workflow():
	if frappe.db.exists("Workflow", "SO Test Workflow"):
		doc = frappe.get_doc("Workflow", "SO Test Workflow")
		doc.set("is_active", 1)
		doc.save()
		return doc

	frappe.get_doc(dict(doctype="Role", role_name="Test Junior Approver")).insert(ignore_if_duplicate=True)
	frappe.get_doc(dict(doctype="Role", role_name="Test Approver")).insert(ignore_if_duplicate=True)
	frappe.cache().hdel("roles", frappe.session.user)

	workflow = frappe.get_doc(
		{
			"doctype": "Workflow",
			"workflow_name": "SO Test Workflow",
			"document_type": "Sales Order",
			"workflow_state_field": "workflow_state",
			"is_active": 1,
			"send_email_alert": 0,
		}
	)
	workflow.append("states", dict(state="Pending", allow_edit="All"))
	workflow.append("states", dict(state="Approved", allow_edit="Test Approver", doc_status=1))
	workflow.append(
		"transitions",
		dict(
			state="Pending",
			action="Approve",
			next_state="Approved",
			allowed="Test Junior Approver",
			allow_self_approval=1,
			condition="doc.grand_total < 200",
		),
	)
	workflow.append(
		"transitions",
		dict(
			state="Pending",
			action="Approve",
			next_state="Approved",
			allowed="Test Approver",
			allow_self_approval=1,
			condition="doc.grand_total > 200",
		),
	)
	workflow.insert(ignore_permissions=True)

	return workflow