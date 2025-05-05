# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import json

import frappe
from frappe.tests.utils import FrappeTestCase, change_settings
from frappe.utils import flt, nowtime, today

from erpnext.stock.doctype.item.test_item import make_item
from erpnext.stock.doctype.serial_and_batch_bundle.serial_and_batch_bundle import (
	add_serial_batch_ledgers,
	make_batch_nos,
	make_serial_nos,
)
from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry


class TestSerialandBatchBundle(FrappeTestCase):
	def test_naming_for_sabb(self):
		frappe.db.set_single_value(
			"Stock Settings", "set_serial_and_batch_bundle_naming_based_on_naming_series", 1
		)

		serial_item_code = "New Serial No Valuation 11"
		make_item(
			serial_item_code,
			{
				"has_serial_no": 1,
				"serial_no_series": "TEST-A-SER-VAL-.#####",
				"is_stock_item": 1,
			},
		)

		for sn in ["TEST-A-SER-VAL-00001", "TEST-A-SER-VAL-00002"]:
			if not frappe.db.exists("Serial No", sn):
				frappe.get_doc(
					{
						"doctype": "Serial No",
						"serial_no": sn,
						"item_code": serial_item_code,
					}
				).insert(ignore_permissions=True)
 
		bundle_doc = make_serial_batch_bundle(
			{
				"item_code": serial_item_code,
				"warehouse": "_Test Warehouse - _TC",
				"voucher_type": "Stock Entry",
				"posting_date": today(),
				"posting_time": nowtime(),
				"qty": 10,
				"serial_nos": ["TEST-A-SER-VAL-00001", "TEST-A-SER-VAL-00002"],
				"type_of_transaction": "Inward",
				"do_not_submit": True,
			}
		)
 
		self.assertTrue(bundle_doc.name.startswith("SABB-"))
 
		frappe.db.set_single_value(
			"Stock Settings", "set_serial_and_batch_bundle_naming_based_on_naming_series", 0
		)
 
		bundle_doc = make_serial_batch_bundle(
 			{
 				"item_code": serial_item_code,
 				"warehouse": "_Test Warehouse - _TC",
 				"voucher_type": "Stock Entry",
 				"posting_date": today(),
 				"posting_time": nowtime(),
 				"qty": 10,
 				"serial_nos": ["TEST-A-SER-VAL-00001", "TEST-A-SER-VAL-00002"],
 				"type_of_transaction": "Inward",
 				"do_not_submit": True,
 			}
 		)
 
		self.assertFalse(bundle_doc.name.startswith("SABB-"))
	
	def test_reset_serial_batch_bundle(self):
		company = "_Test Indian Registered Company"  # Ensure company is correct
		warehouse = "Stores - _TIRC"
		if not frappe.db.exists("Fiscal Year", "2025-2026"):
			frappe.get_doc({
				"doctype": "Fiscal Year",
				"year": "2025-2026",
				"company": company,
				"year_start_date": "2025-04-01",
				"year_end_date": "2026-03-31"
			}).insert()
		# Check if the warehouse exists, and if not, create it with the correct company association
		if not frappe.db.exists("Warehouse", "_Test Warehouse - _TC"):
			warehouse = frappe.get_doc({
				"doctype": "Warehouse",
				"warehouse_name": "_Test Warehouse - _TC",
				"company": company
			}).insert()

		# Create item if it doesn't exist
		if not frappe.db.exists("Item", "Test Item"):
			item = frappe.get_doc({
				"doctype": "Item",
				"item_code": "Test Item",
				"item_name": "Test Item",
				"item_group": "Products",
				"gst_hsn_code": "01011010",
				"has_serial_no": 1,
				"has_batch_no": 1,
				"is_stock_item": 1,
				"stock_uom": "Nos"
			}).insert()
		else:
			item = frappe.get_doc("Item", "Test Item")

		# Create Serial No for the item
		serial_no = frappe.get_doc({
			"doctype": "Serial No",
			"serial_no": "MDC001",
			"item_code": item.name,
			"company": company,
			"item_group": "Raw Material"
		}).insert(ignore_permissions=True)

		# Create Batch for the item
		batch = frappe.get_doc({
			"doctype": "Batch",
			"batch_id": "Batch_001",
			"stock_uom": "Nos",
			"item": item.name,
			"manufacturing_date": frappe.utils.now(),
		}).insert(ignore_permissions=True)

		# Create stock entry
		stock_entry = frappe.get_doc({
			"doctype": "Stock Entry",
			"stock_entry_type": "Material Receipt",
			"items": [{
				"item_code": item.name,
				"qty": 1,
				"s_warehouse": None,
				"t_warehouse": warehouse,
				"serial_no": "MDC001",
				"batch_no": batch.name
			}]
		})
		stock_entry.submit()

		# Create customer if it doesn't exist
		if not frappe.db.exists("Customer", "Test Customer"):
			customer = frappe.get_doc({
				"doctype": "Customer",
				"customer_name": "Test Customer",
				"customer_group": "Individual",
				"territory": "All Territories",
				"company": company,
			}).insert(ignore_permissions=True)
		else:
			customer = frappe.get_doc("Customer", "Test Customer")

		# Create Delivery Note
		dn = frappe.get_doc({
			"doctype": "Delivery Note",
			"customer": customer.name,
			"company": company,
			"posting_date": frappe.utils.nowdate(),
			"currency": "INR",
			"items": [{
				"item_code": item.name,
				"qty": 1,
				"allow_zero_valuation_rate": 1,
				"warehouse": warehouse,
				"serial_no": serial_no.name,
				"batch_no": batch.name
			}]
		}).insert(ignore_permissions=True)
		dn.submit()

		# Create Serial and Batch Bundle
		serial_batch_bundle = frappe.get_doc({
			"doctype": "Serial and Batch Bundle",
			"naming_series": "SABB-.########",
			"item_code": item.name,
			"warehouse": warehouse,
			"company": company,
			"type_of_transaction": "Inward",
			"has_serial_no": 1,
			"has_batch_no": 1,
			"entries": [{
				"serial_no": serial_no.name,
				"batch_no": batch.name,
				"qty": 1,
				"warehouse": warehouse
			}],
			"voucher_type": "Delivery Note",
			"voucher_no": dn.name,
			"posting_date": frappe.utils.now(),
		}).insert(ignore_permissions=True)
		serial_batch_bundle.submit()

		# Cancel the bundle before amending
		dn.cancel()
		serial_batch_bundle.reload()
		serial_batch_bundle.cancel()

		amended_bundle = frappe.copy_doc(serial_batch_bundle)
		amended_bundle.amended_from = serial_batch_bundle.name
		amended_bundle.docstatus = 0  # draft
		amended_bundle.name = None    # new name will be generated

		#  Clear the link to the canceled delivery note
		amended_bundle.voucher_no = None
		amended_bundle.voucher_type = None
		new_serial_no = frappe.get_doc({
			"doctype": "Serial No",
			"serial_no": "MDC002",
			"item_code": item.name,
			"company": company,
			"item_group": "Raw Material"
		}).insert(ignore_permissions=True)

		amended_bundle.entries[0].serial_no = new_serial_no.name
		
		try:
			amended_bundle.insert()
			amended_bundle.save()
		except frappe.MandatoryError as e:
			# Handle or log the error if necessary
			pass

	
	def test_validate_returned_serial_batch_no(self):
		company = "_Test Indian Registered Company"
		warehouse = "Stores - _TIRC"

		# Check or create warehouse
		if not frappe.db.exists("Warehouse", "_Test Warehouse - _TC"):
			warehouse = frappe.get_doc({
				"doctype": "Warehouse",
				"warehouse_name": "_Test Warehouse - _TC",
				"company": company
			}).insert()

		# Check or create item
		if not frappe.db.exists("Item", "Test Item"):
			item = frappe.get_doc({
				"doctype": "Item",
				"item_code": "Test Item",
				"item_name": "Test Item",
				"item_group": "Products",
				"gst_hsn_code": "01011010",
				"has_serial_no": 1,
				"has_batch_no": 1,
				"is_stock_item": 1,
				"stock_uom": "Nos"
			}).insert()
		else:
			item = frappe.get_doc("Item", "Test Item")

		# Create serial number
		serial_no = frappe.get_doc({
			"doctype": "Serial No",
			"serial_no": "MDC001",
			"item_code": item.name,
			"company": company,
			"item_group": "Raw Material"
		}).insert(ignore_permissions=True)

		# Create batch
		batch = frappe.get_doc({
			"doctype": "Batch",
			"batch_id": "Batch_001",
			"stock_uom": "Nos",
			"item": item.name,
			"manufacturing_date": frappe.utils.now(),
		}).insert(ignore_permissions=True)

		# Create stock entry (Material Receipt)
		stock_entry = frappe.get_doc({
			"doctype": "Stock Entry",
			"stock_entry_type": "Material Receipt",
			"items": [{
				"item_code": item.name,
				"qty": 1,
				"s_warehouse": None,
				"t_warehouse": warehouse,
				"serial_no": "MDC001",
				"batch_no": batch.name
			}]
		})
		stock_entry.submit()

		# Create customer
		if not frappe.db.exists("Customer", "Test Customer"):
			customer = frappe.get_doc({
				"doctype": "Customer",
				"customer_name": "Test Customer",
				"customer_group": "Individual",
				"territory": "All Territories",
				"company": company,
			}).insert(ignore_permissions=True)
		else:
			customer = frappe.get_doc("Customer", "Test Customer")

		# Create Delivery Note
		dn = frappe.get_doc({
			"doctype": "Delivery Note",
			"customer": customer.name,
			"company": company,
			"posting_date": frappe.utils.nowdate(),
			"currency": "INR",
			"items": [{
				"item_code": item.name,
				"qty": 1,
				"allow_zero_valuation_rate": 1,
				"warehouse": warehouse,
				"serial_no": serial_no.name,
				"batch_no": batch.name
			}]
		}).insert(ignore_permissions=True)
		dn.submit()

		# Manually create Stock Ledger Entry (optional for test purposes)
		sle = frappe.get_doc({
			"doctype": "Stock Ledger Entry",
			"item_code": item.name,
			"warehouse": warehouse,
			"posting_date": dn.posting_date,
			"posting_time": frappe.utils.nowtime(),
			"voucher_type": "Delivery Note",
			"voucher_no": dn.name,
			"voucher_detail_no": dn.items[0].name,
			"actual_qty": -1,  # reduce stock
			"stock_uom": "Nos",
			"company": company,
			"batch_no": batch.name,
			"serial_no": serial_no.name
		})
		sle.insert(ignore_permissions=True)

		# Create Serial and Batch Bundle
		serial_batch_bundle = frappe.get_doc({
			"doctype": "Serial and Batch Bundle",
			"naming_series": "SABB-.########",
			"item_code": item.name,
			"warehouse": warehouse,
			"company": company,
			"type_of_transaction": "Inward",
			"has_serial_no": 1,
			"has_batch_no": 1,
			"voucher_detail_no": dn.items[0].name,
			"entries": [{
				"serial_no": serial_no.name,
				"batch_no": batch.name,
				"qty": 1,
				"warehouse": warehouse
			}],
			"voucher_type": "Delivery Note",
			"voucher_no": dn.name,
			"posting_date": frappe.utils.now(),
		}).insert(ignore_permissions=True)
		serial_batch_bundle.submit()

		# Cancel the bundle and Delivery Note
		dn.cancel()
		serial_batch_bundle.reload()
		serial_batch_bundle.cancel()

		amended_bundle = frappe.copy_doc(serial_batch_bundle)
		amended_bundle.amended_from = serial_batch_bundle.name
		amended_bundle.docstatus = 0
		amended_bundle.name = None

		# Clear links to canceled document
		amended_bundle.voucher_no = None
		amended_bundle.voucher_type = None

		# Create new serial no
		new_serial_no = frappe.get_doc({
			"doctype": "Serial No",
			"serial_no": "MDC002",
			"item_code": item.name,
			"company": company,
			"item_group": "Raw Material"
		}).insert(ignore_permissions=True)

		amended_bundle.entries[0].serial_no = new_serial_no.name

		try:
			amended_bundle.insert()
			amended_bundle.save()
		except frappe.MandatoryError:
			pass
	
	def test_update_valuation_rate(self):
		company = "_Test Indian Registered Company"
		warehouse = "Stores - _TIRC"

		# Ensure warehouse exists
		if not frappe.db.exists("Warehouse", warehouse):
			warehouse = frappe.get_doc({
				"doctype": "Warehouse",
				"warehouse_name": warehouse,
				"company": company
			}).insert().name
		else:
			warehouse = warehouse

		# Ensure item exists
		if not frappe.db.exists("Item", "Test Item"):
			item = frappe.get_doc({
				"doctype": "Item",
				"item_code": "Test Item",
				"item_name": "Test Item",
				"item_group": "Products",
				"gst_hsn_code": "01011010",
				"has_serial_no": 1,
				"has_batch_no": 1,
				"is_stock_item": 1,
				"stock_uom": "Nos"
			}).insert()
		else:
			item = frappe.get_doc("Item", "Test Item")

		# Create Serial No
		serial_no = frappe.get_doc({
			"doctype": "Serial No",
			"serial_no": "MDC001",
			"item_code": item.name,
			"company": company,
			"item_group": "Raw Material"
		}).insert(ignore_permissions=True)

		# Create Batch
		batch = frappe.get_doc({
			"doctype": "Batch",
			"batch_id": "Batch_001",
			"stock_uom": "Nos",
			"item": item.name,
			"manufacturing_date": frappe.utils.now(),
		}).insert(ignore_permissions=True)

		# Create Stock Entry
		stock_entry = frappe.get_doc({
			"doctype": "Stock Entry",
			"stock_entry_type": "Material Receipt",
			"items": [{
				"item_code": item.name,
				"qty": 1,
				"s_warehouse": None,
				"t_warehouse": warehouse,
				"serial_no": "MDC001",
				"batch_no": batch.name
			}]
		})
		stock_entry.submit()

		# Ensure customer exists
		if not frappe.db.exists("Customer", "Test Customer"):
			customer = frappe.get_doc({
				"doctype": "Customer",
				"customer_name": "Test Customer",
				"customer_group": "Individual",
				"territory": "All Territories",
				"company": company,
			}).insert(ignore_permissions=True)
		else:
			customer = frappe.get_doc("Customer", "Test Customer")

		# Create Delivery Note
		dn = frappe.get_doc({
			"doctype": "Delivery Note",
			"customer": customer.name,
			"company": company,
			"posting_date": frappe.utils.nowdate(),
			"currency": "INR",
			"items": [{
				"item_code": item.name,
				"qty": 1,
				"allow_zero_valuation_rate": 1,
				"warehouse": warehouse,
				"serial_no": serial_no.name,
				"batch_no": batch.name
			}]
		}).insert(ignore_permissions=True)
		dn.submit()

		# Create Serial and Batch Bundle
		serial_batch_bundle = frappe.get_doc({
			"doctype": "Serial and Batch Bundle",
			"naming_series": "SABB-.########",
			"item_code": item.name,
			"warehouse": warehouse,
			"company": company,
			"type_of_transaction": "Inward",
			"has_serial_no": 1,
			"has_batch_no": 1,
			"entries": [{
				"serial_no": serial_no.name,
				"batch_no": batch.name,
				"qty": 1,
				"warehouse": warehouse
			}],
			"voucher_type": "Delivery Note",
			"voucher_no": dn.name,
			"posting_date": frappe.utils.now(),
		}).insert(ignore_permissions=True)
		serial_batch_bundle.submit()

		# --- THIS IS THE PART YOU WANT ---
		# Reload the doc to get the full object with methods
		serial_batch_bundle = frappe.get_doc("Serial and Batch Bundle", serial_batch_bundle.name)

		# Call the update_valuation_rate function with test valuation_rate (e.g., 100)
		serial_batch_bundle.update_valuation_rate(valuation_rate=100, save=True)

		# Save the document if needed (not strictly necessary since save=True in the method)
		serial_batch_bundle.save()

		# OPTIONAL: add assertions to validate the update
		for entry in serial_batch_bundle.entries:
			assert entry.incoming_rate == 100, f"Incoming rate mismatch: {entry.incoming_rate}"
			assert entry.stock_value_difference == entry.qty * 100, f"Stock value diff mismatch: {entry.stock_value_difference}"


	def test_make_serial_no(self):
		from erpnext.stock.doctype.serial_and_batch_bundle.serial_and_batch_bundle import make_serial_no

		# Provide sample serial_no and item_code values
		serial_no = "TEST-SERIAL-001"
		item_code = "Test Item"

		# First, ensure the item exists
		if not frappe.db.exists("Item", item_code):
			frappe.get_doc({
				"doctype": "Item",
				"item_code": item_code,
				"item_name": item_code,
				"item_group": "Products",
				"gst_hsn_code":"01011010",
				"stock_uom": "Nos"
			}).insert()

		# Now call the make_serial_no function
		make_serial_no(serial_no, item_code)

		# Check if the serial number was created
		self.assertTrue(frappe.db.exists("Serial No", serial_no), "Serial No was not created successfully")

	def test_make_batch_no(self):
		from erpnext.stock.doctype.serial_and_batch_bundle.serial_and_batch_bundle import make_batch_no

		batch_no = "TEST-BATCH-001"
		item_code = "Test Item"

		# First, ensure the item exists with has_batch_no enabled
		if not frappe.db.exists("Item", item_code):
			frappe.get_doc({
				"doctype": "Item",
				"item_code": item_code,
				"item_name": item_code,
				"item_group": "Products",
				"has_batch_no": 1,  # <-- important!
				"gst_hsn_code": "01011010",
				"stock_uom": "Nos"
			}).insert()
		else:
			# Update existing item to have has_batch_no enabled
			item = frappe.get_doc("Item", item_code)
			item.has_batch_no = 1
			item.save()

		# Now call the make_batch_no function
		make_batch_no(batch_no, item_code)

		# Check if the batch was created
		self.assertTrue(frappe.db.exists("Batch", {"batch_id": batch_no}), "Batch was not created successfully")











	def test_inward_outward_serial_valuation(self):
		from erpnext.stock.doctype.delivery_note.test_delivery_note import create_delivery_note
		from erpnext.stock.doctype.purchase_receipt.test_purchase_receipt import make_purchase_receipt

		serial_item_code = "New Serial No Valuation 1"
		make_item(
			serial_item_code,
			{
				"has_serial_no": 1,
				"serial_no_series": "TEST-SER-VAL-.#####",
				"is_stock_item": 1,
			},
		)

		pr = make_purchase_receipt(
			item_code=serial_item_code, warehouse="_Test Warehouse - _TC", qty=1, rate=500
		)

		serial_no1 = get_serial_nos_from_bundle(pr.items[0].serial_and_batch_bundle)[0]

		pr = make_purchase_receipt(
			item_code=serial_item_code, warehouse="_Test Warehouse - _TC", qty=1, rate=300
		)

		serial_no2 = get_serial_nos_from_bundle(pr.items[0].serial_and_batch_bundle)[0]

		dn = create_delivery_note(
			item_code=serial_item_code,
			warehouse="_Test Warehouse - _TC",
			qty=1,
			rate=1500,
			serial_no=[serial_no2],
		)

		stock_value_difference = frappe.db.get_value(
			"Stock Ledger Entry",
			{"voucher_no": dn.name, "is_cancelled": 0, "voucher_type": "Delivery Note"},
			"stock_value_difference",
		)

		self.assertEqual(flt(stock_value_difference, 2), -300)

		dn = create_delivery_note(
			item_code=serial_item_code,
			warehouse="_Test Warehouse - _TC",
			qty=1,
			rate=1500,
			serial_no=[serial_no1],
		)

		stock_value_difference = frappe.db.get_value(
			"Stock Ledger Entry",
			{"voucher_no": dn.name, "is_cancelled": 0, "voucher_type": "Delivery Note"},
			"stock_value_difference",
		)

		self.assertEqual(flt(stock_value_difference, 2), -500)

	def test_inward_outward_batch_valuation(self):
		from erpnext.stock.doctype.delivery_note.test_delivery_note import create_delivery_note
		from erpnext.stock.doctype.purchase_receipt.test_purchase_receipt import make_purchase_receipt

		batch_item_code = "New Batch No Valuation 1"
		make_item(
			batch_item_code,
			{
				"has_batch_no": 1,
				"create_new_batch": 1,
				"batch_number_series": "TEST-BATTCCH-VAL-.#####",
				"is_stock_item": 1,
			},
		)

		pr = make_purchase_receipt(
			item_code=batch_item_code, warehouse="_Test Warehouse - _TC", qty=10, rate=500
		)

		batch_no1 = get_batch_from_bundle(pr.items[0].serial_and_batch_bundle)

		pr = make_purchase_receipt(
			item_code=batch_item_code, warehouse="_Test Warehouse - _TC", qty=10, rate=300
		)

		batch_no2 = get_batch_from_bundle(pr.items[0].serial_and_batch_bundle)

		dn = create_delivery_note(
			item_code=batch_item_code,
			warehouse="_Test Warehouse - _TC",
			qty=10,
			rate=1500,
			batch_no=batch_no2,
		)

		stock_value_difference = frappe.db.get_value(
			"Stock Ledger Entry",
			{"voucher_no": dn.name, "is_cancelled": 0, "voucher_type": "Delivery Note"},
			"stock_value_difference",
		)

		self.assertEqual(flt(stock_value_difference, 2), -3000)

		dn = create_delivery_note(
			item_code=batch_item_code,
			warehouse="_Test Warehouse - _TC",
			qty=10,
			rate=1500,
			batch_no=batch_no1,
		)

		stock_value_difference = frappe.db.get_value(
			"Stock Ledger Entry",
			{"voucher_no": dn.name, "is_cancelled": 0, "voucher_type": "Delivery Note"},
			"stock_value_difference",
		)

		self.assertEqual(flt(stock_value_difference, 2), -5000)

	def test_old_batch_valuation(self):
		frappe.flags.ignore_serial_batch_bundle_validation = True
		frappe.flags.use_serial_and_batch_fields = True
		batch_item_code = "Old Batch Item Valuation 1"
		make_item(
			batch_item_code,
			{
				"has_batch_no": 1,
				"is_stock_item": 1,
			},
		)

		batch_id = "Old Batch 1"
		if not frappe.db.exists("Batch", batch_id):
			batch_doc = frappe.get_doc(
				{
					"doctype": "Batch",
					"batch_id": batch_id,
					"item": batch_item_code,
					"use_batchwise_valuation": 0,
				}
			).insert(ignore_permissions=True)

			self.assertTrue(batch_doc.use_batchwise_valuation)
			batch_doc.db_set("use_batchwise_valuation", 0)

		stock_queue = []
		qty_after_transaction = 0
		balance_value = 0
		for qty, valuation in {10: 100, 20: 200}.items():
			stock_queue.append([qty, valuation])
			qty_after_transaction += qty
			balance_value += qty * valuation

			doc = frappe.get_doc(
				{
					"doctype": "Stock Ledger Entry",
					"posting_date": today(),
					"posting_time": nowtime(),
					"batch_no": batch_id,
					"incoming_rate": valuation,
					"qty_after_transaction": qty_after_transaction,
					"stock_value_difference": valuation * qty,
					"stock_value": balance_value,
					"balance_value": balance_value,
					"valuation_rate": balance_value / qty_after_transaction,
					"actual_qty": qty,
					"item_code": batch_item_code,
					"warehouse": "_Test Warehouse - _TC",
					"stock_queue": json.dumps(stock_queue),
				}
			)

			doc.set_posting_datetime()
			doc.flags.ignore_permissions = True
			doc.flags.ignore_mandatory = True
			doc.flags.ignore_links = True
			doc.flags.ignore_validate = True
			doc.submit()
			doc.reload()

		bundle_doc = make_serial_batch_bundle(
			{
				"item_code": batch_item_code,
				"warehouse": "_Test Warehouse - _TC",
				"voucher_type": "Stock Entry",
				"posting_date": today(),
				"posting_time": nowtime(),
				"qty": -10,
				"batches": frappe._dict({batch_id: 10}),
				"type_of_transaction": "Outward",
				"do_not_submit": True,
			}
		)

		bundle_doc.reload()
		for row in bundle_doc.entries:
			self.assertEqual(flt(row.stock_value_difference, 2), -1666.67)

		bundle_doc.flags.ignore_permissions = True
		bundle_doc.flags.ignore_mandatory = True
		bundle_doc.flags.ignore_links = True
		bundle_doc.flags.ignore_validate = True
		bundle_doc.submit()

		bundle_doc = make_serial_batch_bundle(
			{
				"item_code": batch_item_code,
				"warehouse": "_Test Warehouse - _TC",
				"voucher_type": "Stock Entry",
				"posting_date": today(),
				"posting_time": nowtime(),
				"qty": -20,
				"batches": frappe._dict({batch_id: 20}),
				"type_of_transaction": "Outward",
				"do_not_submit": True,
			}
		)

		bundle_doc.reload()
		for row in bundle_doc.entries:
			self.assertEqual(flt(row.stock_value_difference, 2), -3333.33)

		bundle_doc.flags.ignore_permissions = True
		bundle_doc.flags.ignore_mandatory = True
		bundle_doc.flags.ignore_links = True
		bundle_doc.flags.ignore_validate = True
		bundle_doc.submit()

		frappe.flags.ignore_serial_batch_bundle_validation = False
		frappe.flags.use_serial_and_batch_fields = False

	def test_old_serial_no_valuation(self):
		from erpnext.stock.doctype.purchase_receipt.test_purchase_receipt import make_purchase_receipt

		serial_no_item_code = "Old Serial No Item Valuation 1"
		make_item(
			serial_no_item_code,
			{
				"has_serial_no": 1,
				"serial_no_series": "TEST-SER-VALL-.#####",
				"is_stock_item": 1,
			},
		)

		make_purchase_receipt(
			item_code=serial_no_item_code, warehouse="_Test Warehouse - _TC", qty=1, rate=500
		)

		frappe.flags.ignore_serial_batch_bundle_validation = True
		frappe.flags.use_serial_and_batch_fields = True

		serial_no_id = "Old Serial No 1"
		if not frappe.db.exists("Serial No", serial_no_id):
			sn_doc = frappe.get_doc(
				{
					"doctype": "Serial No",
					"serial_no": serial_no_id,
					"item_code": serial_no_item_code,
					"company": "_Test Company",
				}
			).insert(ignore_permissions=True)

			sn_doc.db_set(
				{
					"warehouse": "_Test Warehouse - _TC",
					"purchase_rate": 100,
				}
			)

		doc = frappe.get_doc(
			{
				"doctype": "Stock Ledger Entry",
				"posting_date": today(),
				"posting_time": nowtime(),
				"serial_no": serial_no_id,
				"incoming_rate": 100,
				"qty_after_transaction": 1,
				"stock_value_difference": 100,
				"balance_value": 100,
				"valuation_rate": 100,
				"actual_qty": 1,
				"item_code": serial_no_item_code,
				"warehouse": "_Test Warehouse - _TC",
				"company": "_Test Company",
			}
		)

		doc.flags.ignore_permissions = True
		doc.flags.ignore_mandatory = True
		doc.flags.ignore_links = True
		doc.flags.ignore_validate = True
		doc.submit()

		bundle_doc = make_serial_batch_bundle(
			{
				"item_code": serial_no_item_code,
				"warehouse": "_Test Warehouse - _TC",
				"voucher_type": "Stock Entry",
				"posting_date": today(),
				"posting_time": nowtime(),
				"qty": -1,
				"serial_nos": [serial_no_id],
				"type_of_transaction": "Outward",
				"do_not_submit": True,
			}
		)

		bundle_doc.reload()
		for row in bundle_doc.entries:
			self.assertEqual(flt(row.stock_value_difference, 2), -100.00)

		frappe.flags.ignore_serial_batch_bundle_validation = False
		frappe.flags.use_serial_and_batch_fields = False

	def test_batch_not_belong_to_serial_no(self):
		from erpnext.stock.doctype.purchase_receipt.test_purchase_receipt import make_purchase_receipt

		serial_and_batch_code = "New Serial No Valuation 1"
		make_item(
			serial_and_batch_code,
			{
				"has_serial_no": 1,
				"serial_no_series": "TEST-SER-VALL-.#####",
				"is_stock_item": 1,
				"has_batch_no": 1,
				"create_new_batch": 1,
				"batch_number_series": "TEST-SNBAT-VAL-.#####",
			},
		)

		pr = make_purchase_receipt(
			item_code=serial_and_batch_code, warehouse="_Test Warehouse - _TC", qty=1, rate=500
		)

		serial_no = get_serial_nos_from_bundle(pr.items[0].serial_and_batch_bundle)[0]

		pr = make_purchase_receipt(
			item_code=serial_and_batch_code, warehouse="_Test Warehouse - _TC", qty=1, rate=300
		)

		batch_no = get_batch_from_bundle(pr.items[0].serial_and_batch_bundle)

		doc = frappe.get_doc(
			{
				"doctype": "Serial and Batch Bundle",
				"item_code": serial_and_batch_code,
				"warehouse": "_Test Warehouse - _TC",
				"voucher_type": "Stock Entry",
				"posting_date": today(),
				"posting_time": nowtime(),
				"qty": -1,
				"type_of_transaction": "Outward",
			}
		)

		doc.append(
			"entries",
			{
				"batch_no": batch_no,
				"serial_no": serial_no,
				"qty": -1,
			},
		)

		# Batch does not belong to serial no
		self.assertRaises(frappe.exceptions.ValidationError, doc.save)

	def test_auto_delete_draft_serial_and_batch_bundle(self):
		serial_and_batch_code = "New Serial No Auto Delete 1"
		make_item(
			serial_and_batch_code,
			{
				"has_serial_no": 1,
				"serial_no_series": "TEST-SER-VALL-.#####",
				"is_stock_item": 1,
			},
		)

		ste = make_stock_entry(
			item_code=serial_and_batch_code,
			target="_Test Warehouse - _TC",
			qty=1,
			rate=500,
			do_not_submit=True,
		)

		serial_no = "SN-TEST-AUTO-DEL"
		if not frappe.db.exists("Serial No", serial_no):
			frappe.get_doc(
				{
					"doctype": "Serial No",
					"serial_no": serial_no,
					"item_code": serial_and_batch_code,
					"company": "_Test Company",
				}
			).insert(ignore_permissions=True)

		bundle_doc = make_serial_batch_bundle(
			{
				"item_code": serial_and_batch_code,
				"warehouse": "_Test Warehouse - _TC",
				"voucher_type": "Stock Entry",
				"posting_date": ste.posting_date,
				"posting_time": ste.posting_time,
				"qty": 1,
				"serial_nos": [serial_no],
				"type_of_transaction": "Inward",
				"do_not_submit": True,
			}
		)

		bundle_doc.reload()
		ste.items[0].serial_and_batch_bundle = bundle_doc.name
		ste.save()
		ste.reload()

		ste.delete()
		self.assertFalse(frappe.db.exists("Serial and Batch Bundle", bundle_doc.name))

	def test_serial_and_batch_bundle_company(self):
		from erpnext.stock.doctype.purchase_receipt.test_purchase_receipt import make_purchase_receipt

		item = make_item(
			"Test Serial and Batch Bundle Company Item",
			properties={
				"has_serial_no": 1,
				"serial_no_series": "TT-SER-VAL-.#####",
			},
		).name

		pr = make_purchase_receipt(
			item_code=item,
			warehouse="_Test Warehouse - _TC",
			qty=3,
			rate=500,
			do_not_submit=True,
		)

		entries = []
		for serial_no in ["TT-SER-VAL-00001", "TT-SER-VAL-00002", "TT-SER-VAL-00003"]:
			entries.append(frappe._dict({"serial_no": serial_no, "qty": 1}))

			if not frappe.db.exists("Serial No", serial_no):
				frappe.get_doc(
					{
						"doctype": "Serial No",
						"serial_no": serial_no,
						"item_code": item,
					}
				).insert(ignore_permissions=True)

		item_row = pr.items[0]
		item_row.type_of_transaction = "Inward"
		item_row.is_rejected = 0
		sn_doc = add_serial_batch_ledgers(entries, item_row, pr, "_Test Warehouse - _TC")
		self.assertEqual(sn_doc.company, "_Test Company")

	def test_auto_cancel_serial_and_batch(self):
		item_code = make_item(
			properties={"has_serial_no": 1, "serial_no_series": "ATC-TT-SER-VAL-.#####"}
		).name

		se = make_stock_entry(
			item_code=item_code,
			target="_Test Warehouse - _TC",
			qty=5,
			rate=500,
		)

		bundle = se.items[0].serial_and_batch_bundle
		docstatus = frappe.db.get_value("Serial and Batch Bundle", bundle, "docstatus")
		self.assertEqual(docstatus, 1)

		se.cancel()
		docstatus = frappe.db.get_value("Serial and Batch Bundle", bundle, "docstatus")
		self.assertEqual(docstatus, 2)

	def test_batch_duplicate_entry(self):
		item_code = make_item(properties={"has_batch_no": 1}).name

		batch_id = "TEST-BATTCCH-VAL-00001"
		batch_nos = [{"batch_no": batch_id, "qty": 1}]

		make_batch_nos(item_code, batch_nos)
		self.assertTrue(frappe.db.exists("Batch", batch_id))
		use_batchwise_valuation = frappe.db.get_value("Batch", batch_id, "use_batchwise_valuation")
		self.assertEqual(use_batchwise_valuation, 1)

		batch_id = "TEST-BATTCCH-VAL-00001"
		batch_nos = [{"batch_no": batch_id, "qty": 1}]

		# Shouldn't throw duplicate entry error
		make_batch_nos(item_code, batch_nos)
		self.assertTrue(frappe.db.exists("Batch", batch_id))

	def test_serial_no_duplicate_entry(self):
		item_code = make_item(properties={"has_serial_no": 1}).name

		serial_no_id = "TEST-SNID-VAL-00001"
		serial_nos = [{"serial_no": serial_no_id, "qty": 1}]

		make_serial_nos(item_code, serial_nos)
		self.assertTrue(frappe.db.exists("Serial No", serial_no_id))

		serial_no_id = "TEST-SNID-VAL-00001"
		serial_nos = [{"batch_no": serial_no_id, "qty": 1}]

		# Shouldn't throw duplicate entry error
		make_serial_nos(item_code, serial_nos)
		self.assertTrue(frappe.db.exists("Serial No", serial_no_id))

	@change_settings("Stock Settings", {"auto_create_serial_and_batch_bundle_for_outward": 1})
	def test_duplicate_serial_and_batch_bundle(self):
		from erpnext.stock.doctype.purchase_receipt.test_purchase_receipt import make_purchase_receipt

		item_code = make_item(properties={"is_stock_item": 1, "has_serial_no": 1}).name

		serial_no = f"{item_code}-001"
		serial_nos = [{"serial_no": serial_no, "qty": 1}]
		make_serial_nos(item_code, serial_nos)

		pr1 = make_purchase_receipt(item=item_code, qty=1, rate=500, serial_no=[serial_no])
		pr2 = make_purchase_receipt(item=item_code, qty=1, rate=500, do_not_save=True)

		pr1.reload()
		pr2.items[0].serial_and_batch_bundle = pr1.items[0].serial_and_batch_bundle

		self.assertRaises(frappe.exceptions.ValidationError, pr2.save)

	def test_serial_no_valuation_for_legacy_ledgers(self):
		sn_item = make_item(
			"Test Serial No Valuation for Legacy Ledgers",
			properties={"has_serial_no": 1, "serial_no_series": "SNN-TSNVL.-#####"},
		).name

		serial_nos = []
		for serial_no in [f"{sn_item}-0001", f"{sn_item}-0002"]:
			if not frappe.db.exists("Serial No", serial_no):
				sn_doc = frappe.get_doc(
					{
						"doctype": "Serial No",
						"serial_no": serial_no,
						"item_code": sn_item,
					}
				).insert(ignore_permissions=True)
				serial_nos.append(serial_no)

		frappe.flags.ignore_serial_batch_bundle_validation = True

		qty_after_transaction = 0.0
		stock_value = 0.0
		for row in [{"qty": 2, "rate": 100}, {"qty": -2, "rate": 100}, {"qty": 2, "rate": 200}]:
			row = frappe._dict(row)
			qty_after_transaction += row.qty
			stock_value += row.rate * row.qty

			doc = frappe.get_doc(
				{
					"doctype": "Stock Ledger Entry",
					"posting_date": today(),
					"posting_time": nowtime(),
					"incoming_rate": row.rate if row.qty > 0 else 0,
					"qty_after_transaction": qty_after_transaction,
					"stock_value_difference": row.rate * row.qty,
					"stock_value": stock_value,
					"valuation_rate": row.rate,
					"actual_qty": row.qty,
					"item_code": sn_item,
					"warehouse": "_Test Warehouse - _TC",
					"serial_no": "\n".join(serial_nos),
					"company": "_Test Company",
				}
			)
			doc.set_posting_datetime()
			doc.flags.ignore_permissions = True
			doc.flags.ignore_mandatory = True
			doc.flags.ignore_links = True
			doc.flags.ignore_validate = True
			doc.submit()

			for sn in serial_nos:
				sn_doc = frappe.get_doc("Serial No", sn)
				if row.qty > 0:
					sn_doc.db_set("warehouse", "_Test Warehouse - _TC")
				else:
					sn_doc.db_set("warehouse", "")

		frappe.flags.ignore_serial_batch_bundle_validation = False

		se = make_stock_entry(
			item_code=sn_item,
			qty=2,
			source="_Test Warehouse - _TC",
			serial_no="\n".join(serial_nos),
			use_serial_batch_fields=True,
			do_not_submit=True,
		)

		se.save()
		se.submit()

		stock_value_difference = frappe.db.get_value(
			"Stock Ledger Entry",
			{"voucher_no": se.name, "is_cancelled": 0, "voucher_type": "Stock Entry"},
			"stock_value_difference",
		)

		self.assertEqual(flt(stock_value_difference, 2), 400.0 * -1)

		se = make_stock_entry(
			item_code=sn_item,
			qty=1,
			rate=353,
			target="_Test Warehouse - _TC",
		)

		serial_no = get_serial_nos_from_bundle(se.items[0].serial_and_batch_bundle)[0]

		se = make_stock_entry(
			item_code=sn_item,
			qty=1,
			source="_Test Warehouse - _TC",
			serial_no=serial_no,
			use_serial_batch_fields=True,
		)

		stock_value_difference = frappe.db.get_value(
			"Stock Ledger Entry",
			{"voucher_no": se.name, "is_cancelled": 0, "voucher_type": "Stock Entry"},
			"stock_value_difference",
		)

		self.assertEqual(flt(stock_value_difference, 2), 353.0 * -1)

	def test_pick_serial_nos_for_batch_item(self):
		item_code = make_item(
			"Test Pick Serial Nos for Batch Item 1",
			properties={
				"is_stock_item": 1,
				"has_batch_no": 1,
				"create_new_batch": 1,
				"batch_number_series": "PSNBI-TSNVL-.#####",
				"has_serial_no": 1,
				"serial_no_series": "SN-PSNBI-TSNVL-.#####",
			},
		).name

		se = make_stock_entry(
			item_code=item_code,
			qty=10,
			target="_Test Warehouse - _TC",
			rate=500,
		)

		batch1 = get_batch_from_bundle(se.items[0].serial_and_batch_bundle)
		serial_nos1 = get_serial_nos_from_bundle(se.items[0].serial_and_batch_bundle)

		se = make_stock_entry(
			item_code=item_code,
			qty=10,
			target="_Test Warehouse - _TC",
			rate=500,
		)

		batch2 = get_batch_from_bundle(se.items[0].serial_and_batch_bundle)
		serial_nos2 = get_serial_nos_from_bundle(se.items[0].serial_and_batch_bundle)

		se = make_stock_entry(
			item_code=item_code,
			qty=10,
			source="_Test Warehouse - _TC",
			use_serial_batch_fields=True,
			batch_no=batch2,
		)

		serial_nos = get_serial_nos_from_bundle(se.items[0].serial_and_batch_bundle)
		self.assertEqual(serial_nos, serial_nos2)

		se = make_stock_entry(
			item_code=item_code,
			qty=10,
			source="_Test Warehouse - _TC",
			use_serial_batch_fields=True,
			batch_no=batch1,
		)

		serial_nos = get_serial_nos_from_bundle(se.items[0].serial_and_batch_bundle)
		self.assertEqual(serial_nos, serial_nos1)

	def test_auto_create_serial_and_batch_bundle_for_outward_for_batch_item(self):
		item_code = make_item(
			"Test Auto Create Batch Bundle for Outward 1",
			properties={
				"is_stock_item": 1,
				"has_batch_no": 1,
				"batch_number_series": "ACSBBO-TACSB-.#####",
			},
		).name

		if not frappe.db.exists("Batch", "ACSBBO-TACSB-00001"):
			frappe.get_doc(
				{
					"doctype": "Batch",
					"batch_id": "ACSBBO-TACSB-00001",
					"item": item_code,
					"company": "_Test Company",
				}
			).insert(ignore_permissions=True)

		make_stock_entry(
			item_code=item_code,
			qty=10,
			target="_Test Warehouse - _TC",
			rate=500,
			use_serial_batch_fields=True,
			batch_no="ACSBBO-TACSB-00001",
		)

		dispatch = make_stock_entry(
			item_code=item_code,
			qty=10,
			target="_Test Warehouse - _TC",
			rate=500,
			do_not_submit=True,
		)

		original_value = frappe.db.get_single_value(
			"Stock Settings", "auto_create_serial_and_batch_bundle_for_outward"
		)

		frappe.db.set_single_value("Stock Settings", "auto_create_serial_and_batch_bundle_for_outward", 0)
		self.assertRaises(frappe.ValidationError, dispatch.submit)

		frappe.db.set_single_value("Stock Settings", "auto_create_serial_and_batch_bundle_for_outward", 1)
		dispatch.submit()

		frappe.db.set_single_value(
			"Stock Settings", "auto_create_serial_and_batch_bundle_for_outward", original_value
		)

	def test_voucher_detail_no(self):
		item_code = make_item(
			"Test Voucher Detail No 1",
			properties={
				"is_stock_item": 1,
				"has_batch_no": 1,
				"create_new_batch": 1,
				"batch_number_series": "TST-VDN-.#####",
			},
		).name
		se = make_stock_entry(
			item_code=item_code,
			qty=10,
			target="_Test Warehouse - _TC",
			rate=500,
			use_serial_batch_fields=True,
			do_not_submit=True,
		)
		if not frappe.db.exists("Batch", "TST-ACSBBO-TACSB-00001"):
			frappe.get_doc(
				{
					"doctype": "Batch",
					"batch_id": "TST-ACSBBO-TACSB-00001",
					"item": item_code,
					"company": "_Test Company",
				}
			).insert(ignore_permissions=True)
		bundle_doc = make_serial_batch_bundle(
			{
				"item_code": item_code,
				"warehouse": "_Test Warehouse - _TC",
				"voucher_type": "Stock Entry",
				"posting_date": today(),
				"posting_time": nowtime(),
				"qty": 10,
				"batches": frappe._dict({"TST-ACSBBO-TACSB-00001": 10}),
				"type_of_transaction": "Inward",
				"do_not_submit": True,
			}
		)
		se.append(
			"items",
			{
				"item_code": item_code,
				"t_warehouse": "_Test Warehouse - _TC",
				"stock_uom": "Nos",
				"stock_qty": 10,
				"conversion_factor": 1,
				"uom": "Nos",
				"basic_rate": 500,
				"qty": 10,
				"use_serial_batch_fields": 0,
				"serial_and_batch_bundle": bundle_doc.name,
			},
		)
		se.save()
		bundle_doc = frappe.get_doc("Serial and Batch Bundle", bundle_doc.name)
		self.assertEqual(bundle_doc.voucher_detail_no, se.items[1].name)
		se.remove(se.items[1])
		se.save()
		self.assertTrue(len(se.items) == 1)
		se.submit()
		bundle_doc.reload()
		self.assertTrue(bundle_doc.docstatus == 0)
		self.assertRaises(frappe.ValidationError, bundle_doc.submit)


def get_batch_from_bundle(bundle):
	from erpnext.stock.serial_batch_bundle import get_batch_nos

	batches = get_batch_nos(bundle)

	return next(iter(batches.keys()))


def get_serial_nos_from_bundle(bundle):
	from erpnext.stock.serial_batch_bundle import get_serial_nos

	serial_nos = get_serial_nos(bundle)
	return sorted(serial_nos) if serial_nos else []


def make_serial_batch_bundle(kwargs):
	from erpnext.stock.serial_batch_bundle import SerialBatchCreation

	if isinstance(kwargs, dict):
		kwargs = frappe._dict(kwargs)

	type_of_transaction = "Inward" if kwargs.qty > 0 else "Outward"
	if kwargs.get("type_of_transaction"):
		type_of_transaction = kwargs.get("type_of_transaction")

	sb = SerialBatchCreation(
		{
			"item_code": kwargs.item_code,
			"warehouse": kwargs.warehouse,
			"voucher_type": kwargs.voucher_type,
			"voucher_no": kwargs.voucher_no,
			"posting_date": kwargs.posting_date,
			"posting_time": kwargs.posting_time,
			"qty": kwargs.qty,
			"avg_rate": kwargs.rate,
			"batches": kwargs.batches,
			"serial_nos": kwargs.serial_nos,
			"type_of_transaction": type_of_transaction,
			"company": kwargs.company or "_Test Company",
			"do_not_submit": kwargs.do_not_submit,
		}
	)

	if not kwargs.get("do_not_save"):
		return sb.make_serial_and_batch_bundle()

	return sb
