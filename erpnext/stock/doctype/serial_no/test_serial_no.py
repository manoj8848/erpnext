# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

# ERPNext - web based ERP (http://erpnext.com)
# For license information, please see license.txt


import frappe
from frappe import _dict
from frappe.tests.utils import FrappeTestCase

from erpnext.stock.doctype.delivery_note.test_delivery_note import create_delivery_note
from erpnext.stock.doctype.item.test_item import make_item
from erpnext.stock.doctype.purchase_receipt.test_purchase_receipt import make_purchase_receipt
from erpnext.stock.doctype.serial_and_batch_bundle.test_serial_and_batch_bundle import (
	get_batch_from_bundle,
	get_serial_nos_from_bundle,
)
from erpnext.stock.doctype.serial_no.serial_no import *
from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry
from erpnext.stock.doctype.stock_entry.test_stock_entry import make_serialized_item
from erpnext.stock.doctype.warehouse.test_warehouse import create_warehouse

test_dependencies = ["Item"]
test_records = frappe.get_test_records("Serial No")


class TestSerialNo(FrappeTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_cannot_create_direct(self):
		frappe.delete_doc_if_exists("Serial No", "_TCSER0001")

		sr = frappe.new_doc("Serial No")
		sr.item_code = "_Test Serialized Item"
		sr.warehouse = "_Test Warehouse - _TC"
		sr.serial_no = "_TCSER0001"
		sr.purchase_rate = 10
		self.assertRaises(SerialNoCannotCreateDirectError, sr.insert)

		sr.warehouse = None
		sr.insert()
		self.assertTrue(sr.name)

		sr.warehouse = "_Test Warehouse - _TC"
		self.assertTrue(SerialNoCannotCannotChangeError, sr.save)

	def test_inter_company_transfer(self):
		from erpnext.buying.doctype.purchase_order.test_purchase_order import validate_fiscal_year
		validate_fiscal_year("_Test Company 1")
		validate_fiscal_year("_Test Company")
		se = make_serialized_item(target_warehouse="_Test Warehouse - _TC")
		serial_nos = get_serial_nos_from_bundle(se.get("items")[0].serial_and_batch_bundle)

		create_delivery_note(item_code="_Test Serialized Item With Series", qty=1, serial_no=[serial_nos[0]])

		serial_no = frappe.get_doc("Serial No", serial_nos[0])

		# check Serial No details after delivery
		self.assertEqual(serial_no.warehouse, None)

		wh = create_warehouse("_Test Warehouse", company="_Test Company 1")
		make_purchase_receipt(
			item_code="_Test Serialized Item With Series",
			qty=1,
			serial_no=[serial_nos[0]],
			company="_Test Company 1",
			warehouse=wh,
		)

		serial_no.reload()

		# check Serial No details after purchase in second company
		self.assertEqual(serial_no.warehouse, wh)

	def test_inter_company_transfer_intermediate_cancellation(self):
		"""
		Receive into and Deliver Serial No from one company.
		Then Receive into and Deliver from second company.
		Try to cancel intermediate receipts/deliveries to test if it is blocked.
		"""
		se = make_serialized_item(target_warehouse="_Test Warehouse - _TC")
		serial_nos = get_serial_nos_from_bundle(se.get("items")[0].serial_and_batch_bundle)

		sn_doc = frappe.get_doc("Serial No", serial_nos[0])

		# check Serial No details after purchase in first company
		self.assertEqual(sn_doc.warehouse, "_Test Warehouse - _TC")

		dn = create_delivery_note(
			item_code="_Test Serialized Item With Series", qty=1, serial_no=[serial_nos[0]]
		)
		sn_doc.reload()
		# check Serial No details after delivery from **first** company
		self.assertEqual(sn_doc.warehouse, None)

		# try cancelling the first Serial No Receipt, even though it is delivered
		# block cancellation is Serial No is out of the warehouse
		self.assertRaises(frappe.ValidationError, se.cancel)

		# receive serial no in second company
		wh = create_warehouse("_Test Warehouse", company="_Test Company 1")
		pr = make_purchase_receipt(
			item_code="_Test Serialized Item With Series",
			qty=1,
			serial_no=[serial_nos[0]],
			company="_Test Company 1",
			warehouse=wh,
		)
		sn_doc.reload()

		self.assertEqual(sn_doc.warehouse, wh)
		# try cancelling the delivery from the first company
		# block cancellation as Serial No belongs to different company
		self.assertRaises(frappe.ValidationError, dn.cancel)

		# deliver from second company
		create_delivery_note(
			item_code="_Test Serialized Item With Series",
			qty=1,
			serial_no=[serial_nos[0]],
			company="_Test Company 1",
			warehouse=wh,
		)
		sn_doc.reload()

		# check Serial No details after delivery from **second** company
		self.assertEqual(sn_doc.warehouse, None)

		# cannot cancel any intermediate document before last Delivery Note
		self.assertRaises(frappe.ValidationError, se.cancel)
		self.assertRaises(frappe.ValidationError, dn.cancel)
		self.assertRaises(frappe.ValidationError, pr.cancel)

	def test_inter_company_transfer_fallback_on_cancel(self):
		"""
		Test Serial No state changes on cancellation.
		If Delivery cancelled, it should fall back on last Receipt in the same company.
		If Receipt is cancelled, it should be Inactive in the same company.
		"""
		# Receipt in **first** company
		se = make_serialized_item(target_warehouse="_Test Warehouse - _TC")
		serial_nos = get_serial_nos_from_bundle(se.get("items")[0].serial_and_batch_bundle)
		sn_doc = frappe.get_doc("Serial No", serial_nos[0])

		# Delivery from first company
		dn = create_delivery_note(
			item_code="_Test Serialized Item With Series", qty=1, serial_no=[serial_nos[0]]
		)

		# Receipt in **second** company
		wh = create_warehouse("_Test Warehouse", company="_Test Company 1")
		pr = make_purchase_receipt(
			item_code="_Test Serialized Item With Series",
			qty=1,
			serial_no=[serial_nos[0]],
			company="_Test Company 1",
			warehouse=wh,
		)

		# Delivery from second company
		dn_2 = create_delivery_note(
			item_code="_Test Serialized Item With Series",
			qty=1,
			serial_no=[serial_nos[0]],
			company="_Test Company 1",
			warehouse=wh,
		)
		sn_doc.reload()

		self.assertEqual(sn_doc.warehouse, None)

		dn_2.cancel()
		sn_doc.reload()
		# Fallback on Purchase Receipt if Delivery is cancelled
		self.assertEqual(sn_doc.warehouse, wh)

		pr.cancel()
		sn_doc.reload()
		# Inactive in same company if Receipt cancelled
		self.assertEqual(sn_doc.warehouse, None)

		dn.cancel()
		sn_doc.reload()
		# Fallback on Purchase Receipt in FIRST company if
		# Delivery from FIRST company is cancelled
		self.assertEqual(sn_doc.warehouse, "_Test Warehouse - _TC")

	def test_correct_serial_no_incoming_rate(self):
		"""Check correct consumption rate based on serial no record."""
		item_code = "_Test Serialized Item"
		warehouse = "_Test Warehouse - _TC"
		serial_nos = ["LOWVALUATION", "HIGHVALUATION"]

		for serial_no in serial_nos:
			if not frappe.db.exists("Serial No", serial_no):
				frappe.get_doc(
					{"doctype": "Serial No", "item_code": item_code, "serial_no": serial_no}
				).insert()

		make_stock_entry(
			item_code=item_code, to_warehouse=warehouse, qty=1, rate=42, serial_no=[serial_nos[0]]
		)
		make_stock_entry(
			item_code=item_code, to_warehouse=warehouse, qty=1, rate=113, serial_no=[serial_nos[1]]
		)

		out = create_delivery_note(item_code=item_code, qty=1, serial_no=[serial_nos[0]], do_not_submit=True)

		bundle = out.items[0].serial_and_batch_bundle
		doc = frappe.get_doc("Serial and Batch Bundle", bundle)
		doc.entries[0].serial_no = serial_nos[1]
		doc.save()

		out.save()
		out.submit()

		value_diff = frappe.db.get_value(
			"Stock Ledger Entry",
			{"voucher_no": out.name, "voucher_type": "Delivery Note"},
			"stock_value_difference",
		)
		self.assertEqual(value_diff, -113)

	def test_auto_fetch(self):
		item_code = make_item(
			properties={
				"has_serial_no": 1,
				"has_batch_no": 1,
				"create_new_batch": 1,
				"serial_no_series": "TEST.#######",
			}
		).name
		warehouse = "_Test Warehouse - _TC"

		in1 = make_stock_entry(item_code=item_code, to_warehouse=warehouse, qty=5, rate=500)
		in2 = make_stock_entry(item_code=item_code, to_warehouse=warehouse, qty=5, rate=500)

		in1.reload()
		in2.reload()

		batch1 = get_batch_from_bundle(in1.items[0].serial_and_batch_bundle)
		batch2 = get_batch_from_bundle(in2.items[0].serial_and_batch_bundle)

		batch_wise_serials = {
			batch1: get_serial_nos_from_bundle(in1.items[0].serial_and_batch_bundle),
			batch2: get_serial_nos_from_bundle(in2.items[0].serial_and_batch_bundle),
		}

		# Test FIFO
		first_fetch = get_auto_serial_nos(
			_dict(
				{
					"qty": 5,
					"item_code": item_code,
					"warehouse": warehouse,
				}
			)
		)

		self.assertEqual(first_fetch, batch_wise_serials[batch1])

		# partial FIFO
		partial_fetch = get_auto_serial_nos(
			_dict(
				{
					"qty": 2,
					"item_code": item_code,
					"warehouse": warehouse,
				}
			)
		)

		self.assertTrue(
			set(partial_fetch).issubset(set(first_fetch)),
			msg=f"{partial_fetch} should be subset of {first_fetch}",
		)

		# exclusion
		remaining = get_auto_serial_nos(
			_dict(
				{
					"qty": 3,
					"item_code": item_code,
					"warehouse": warehouse,
					"ignore_serial_nos": partial_fetch,
				}
			)
		)

		self.assertEqual(sorted(remaining + partial_fetch), first_fetch)

		# batchwise
		for batch, expected_serials in batch_wise_serials.items():
			fetched_sr = get_auto_serial_nos(
				_dict({"qty": 5, "item_code": item_code, "warehouse": warehouse, "batches": [batch]})
			)

			self.assertEqual(fetched_sr, sorted(expected_serials))

		# non existing warehouse
		self.assertFalse(
			get_auto_serial_nos(
				_dict({"qty": 10, "item_code": item_code, "warehouse": "Non Existing Warehouse"})
			)
		)

		# multi batch
		all_serials = [sr for sr_list in batch_wise_serials.values() for sr in sr_list]
		fetched_serials = get_auto_serial_nos(
			_dict(
				{
					"qty": 10,
					"item_code": item_code,
					"warehouse": warehouse,
					"batches": list(batch_wise_serials.keys()),
				}
			)
		)
		self.assertEqual(sorted(all_serials), fetched_serials)

		# expiry date
		frappe.db.set_value("Batch", batch1, "expiry_date", "1980-01-01")
		non_expired_serials = get_auto_serial_nos(
			_dict({"qty": 5, "item_code": item_code, "warehouse": warehouse, "batches": [batch1]})
		)

		self.assertEqual(non_expired_serials, [])

	def test_get_pos_reserved_serial_nos_TC_SCK_437(self):
		from erpnext.stock.doctype.warehouse.test_warehouse import create_warehouse
		from erpnext.accounts.doctype.payment_entry.test_payment_entry import create_company
		from erpnext.stock.doctype.item.test_item import (make_item, get_hsn)
		from erpnext.accounts.doctype.cost_center.test_cost_center import create_cost_center
		from erpnext.buying.doctype.purchase_order.test_purchase_order import validate_fiscal_year
		create_company()
		validate_fiscal_year("_Test Company")
		warehouse = create_warehouse("_Test Warehouse", company="_Test Company")
		create_cost_center(cost_center_name="_Test Cost Center", company="_Test Company")

		item_code = "_Test Item POS"

		item = make_item(
			item_code,
			{
				"has_serial_no": 1,
				"serial_no_series": "SN-.#####",
				"is_stock_item": 1,
				"valuation_rate": 500,
				"gst_hsn_code": get_hsn(),
			}
		)
		pos_profile = frappe.get_doc({
		"doctype": "POS Profile",
		"name": "_Test POS Profile New Serial No",
		"company": "_Test Company",
		"currency": "INR",
		"write_off_cost_center": "_Test Cost Center - _TC",
		"write_off_account": "Sales - _TC",
		"warehouse": warehouse,	
		"accounts": [{
			"company": "_Test Company",
			"account": "_Test Account - _TC"  
		}],
		"payments": [{
				"default": 1,
				"mode_of_payment": "Cash",  
				"account": "Cash - _TC"
			}],
		"warehouses": [{
			"warehouse": warehouse
			}]
		})
		pos_profile.insert()

		se = frappe.get_doc({
			"doctype": "Stock Entry",
			"stock_entry_type": "Material Receipt",
			"company": "_Test Company",
			"items": [
				{
					"item_code": item.name,
					"qty": 1,
					"t_warehouse": warehouse
				},
				{
					"item_code": item.name,
					"qty": 1,
					"t_warehouse": warehouse
				}
			]
		})
		se.insert()
		se.submit()

		serial_nos = frappe.get_all("Serial No", filters={"item_code": item.name, "warehouse": warehouse}, fields=["name"])
		serial_no_1 = serial_nos[0].name
		pos_opening_entry = frappe.get_doc({
			"doctype": "POS Opening Entry",
			"pos_profile": pos_profile.name,
			"company": "_Test Company",
			"user": "Administrator",
			"period_start_date": frappe.utils.get_datetime(),
			"mode_of_payment": "Cash",
			"balance_details": [
				{
					"account": "Sales - _TC",
					"mode_of_payment": "Cash",
					"account_currency": "INR",
					"opening_amount": 1000
				}									
			],
			"posting_date": frappe.utils.today(),
			"cash_denominations": [
				{
					"mode_of_payment": "Cash",
					"account": "Cash - _TC",
					"opening_amount": 1000
				}
			]
		})
		pos_opening_entry.insert()
		pos_opening_entry.submit()
		pos_invoice = frappe.get_doc({
			"doctype": "POS Invoice",
			"docstatus": 1,
			"pos_profile": pos_profile.name,
			"company": "_Test Company",
			"cost_center": "_Test Cost Center - _TC",
			"is_return": 0,
			"paid_amount": 1000,
			"items": [{
				"item_code": item.name,
				"warehouse": warehouse,
				"serial_no": serial_no_1,
				"qty": 1
			}],
			"payments": [
				{
					"mode_of_payment": "Cash",
					"account": "Cash - _TC",
					"amount": 1000
				}
			]
		}).insert()

		filters = {
			"item_code": item.name,
			"warehouse": warehouse
		}

		result = get_pos_reserved_serial_nos(filters)
		self.assertIsInstance(result, list)
		self.assertEqual(len(result), 1)
		self.assertEqual(result[0], serial_no_1)

	def test_auto_fetch_serial_number_basic_TC_SCK_438(self):
		from erpnext.stock.doctype.warehouse.test_warehouse import create_warehouse
		from erpnext.accounts.doctype.payment_entry.test_payment_entry import create_company
		from erpnext.stock.doctype.item.test_item import make_item
		from erpnext.accounts.doctype.cost_center.test_cost_center import create_cost_center
		from erpnext.buying.doctype.purchase_order.test_purchase_order import validate_fiscal_year

		create_company("_Test Company")
		validate_fiscal_year("_Test Company")

		warehouse = create_warehouse("_Test Warehouse Auto Fetch", company="_Test Company")

		account = frappe.get_doc({
			"doctype": "Account",
			"account_name": "_Test Inventory Account",
			"parent_account": "Stock Assets - _TC",
			"company": "_Test Company",
			"is_group": 0,
			"account_type": "Stock"
		})
		account.insert()
		frappe.db.set_value("Warehouse", warehouse, "account", account.name)

		item = make_item("_Test Serial Item Auto", {
			"has_serial_no": 1,
			"serial_no_series": "AUTO-SERIAL-.###",
			"is_stock_item": 1,
			"has_batch_no": 1,
			"create_new_batch": 1,
			"batch_no_series": "AUTO-BATCH-.###",
			"valuation_rate": 100
		})

		se = make_stock_entry(
			item_code=item.name,
			qty=2,
			to_warehouse=warehouse,
			company="_Test Company",
			purpose="Material Receipt"
		)
		se.submit()

		batch = frappe.get_all("Batch", {"item": item.name, "reference_name": se.name})
		exclude_sr_nos = ["AUTO-SERIAL-001", "AUTO-SERIAL-002"]
		batch_nos = [d.name for d in batch]

		from erpnext.stock.doctype.serial_no.serial_no import auto_fetch_serial_number
		sr_nos = auto_fetch_serial_number(
			qty=2,
			item_code=item.name,
			warehouse=warehouse,
			exclude_sr_nos=exclude_sr_nos,
			batch_nos=batch_nos
		)

		assert isinstance(sr_nos, list)

  
def get_auto_serial_nos(kwargs):
	from erpnext.stock.doctype.serial_and_batch_bundle.serial_and_batch_bundle import (
		get_available_serial_nos,
	)

	serial_nos = get_available_serial_nos(kwargs)
	return sorted([d.serial_no for d in serial_nos])
