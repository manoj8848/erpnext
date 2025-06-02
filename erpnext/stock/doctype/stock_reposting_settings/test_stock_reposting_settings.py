# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import unittest

import frappe
from datetime import timedelta
from frappe.utils import now_datetime
from erpnext.stock.doctype.repost_item_valuation.repost_item_valuation import get_recipients
from erpnext.setup.doctype.company.test_company import create_child_company
from erpnext.stock.doctype.warehouse.test_warehouse import create_warehouse
from erpnext.accounts.doctype.payment_entry.test_payment_entry import make_test_item
class TestStockRepostingSettings(unittest.TestCase):
	def tearDown(self):
		frappe.db.rollback()

	# codecov
	def test_convert_to_item_wh_reposting_TC_SCK_315(self):
		from erpnext.accounts.doctype.sales_invoice.test_sales_invoice import get_active_fiscal_year

		company = "_Test Indian Registered Company"
		warehouse = "Stores - _TIRC"
		
		from erpnext.accounts.doctype.payment_entry.test_payment_entry import create_customer
		from erpnext.accounts.doctype.purchase_invoice.test_purchase_invoice import make_purchase_invoice	
		from erpnext.stock.doctype.purchase_receipt.test_purchase_receipt import make_purchase_receipt	
		from erpnext.buying.doctype.supplier.test_supplier import create_supplier

		if not frappe.db.exists("Warehouse", warehouse):
			warehouse = create_warehouse(warehouse, company=company)

		customer = "_Test Customer"
		if not frappe.db.exists("Customer", "_Test Customer"):
			create_customer("_Test Customer",currency="INR")

		if not frappe.db.exists("Company", company):
			create_child_company("_Test Indian Registered Company")

		fiscal_year = get_active_fiscal_year()

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
				"serial_no_series": "MDC-.###",
				"is_stock_item": 1,
				"stock_uom": "Nos"
			}).insert()
		else:
			item = frappe.get_doc("Item", "Test Item")
			item.serial_no_series = "MDC-.###"
			item.save()
		assert item.name == "Test Item"
		assert item.has_serial_no == 1
		assert item.has_batch_no == 1

		start_dt = now_datetime()
		end_dt = start_dt + timedelta(hours=1)

		start_time = start_dt.time().strftime("%H:%M:%S")
		end_time = end_dt.time().strftime("%H:%M:%S")

		stock_reposting_setting = frappe.get_doc({
			"doctype": "Stock Reposting Settings",
			"limit_reposting_timeslot": 1,
			"start_time": start_time,  # string like '15:04:52'
			"end_time": end_time,      # string like '16:04:52'
			"limits_dont_apply_on": "Sunday",
			"item_based_reposting": 1,
			"do_reposting_for_each_stock_transaction": 1
		}).insert()

		# Create serial number
		if not frappe.db.exists("Serial No", "MDC001"):
			serial_no = frappe.get_doc({
				"doctype": "Serial No",
				"serial_no": "MDC001",
				"item_code": item.name,
				"company": company,
				"item_group": "Raw Material"
			}).insert(ignore_permissions=True)
		else:
			serial_no = frappe.get_doc("Serial No", "MDC001")

		assert serial_no.name == "MDC001"

		assert serial_no.serial_no == "MDC001"
		assert serial_no.item_code == item.name

		# Create batch
		if not frappe.db.exists("Batch", "Batch_001"):
			batch = frappe.get_doc({
				"doctype": "Batch",
				"batch_id": "Batch_001",
				"stock_uom": "Nos",
				"item": item.name,
				"manufacturing_date": frappe.utils.now(),
			}).insert(ignore_permissions=True)
		else:
			batch = frappe.get_doc("Batch", "Batch_001")
		assert batch.batch_id == "Batch_001"

		location = "Test Location"
		if not frappe.db.exists("Location", location):
			frappe.get_doc({"doctype": "Location", "location_name": location}).insert()

		supplier = "_Test Supplier"
		if not frappe.db.exists("Supplier", supplier):
			create_supplier(supplier_name="_Test Supplier", default_currency="INR")

		# Create stock entry (Material Receipt)
		stock_entry = frappe.get_doc({
			"doctype": "Stock Entry",
			"stock_entry_type": "Material Receipt",
			"company": company,
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

		sle = frappe.get_doc({
			"doctype": "Stock Ledger Entry",
			"item_code": item.name,
			"warehouse": warehouse,
			"posting_date": stock_entry.posting_date,
			"posting_time": frappe.utils.nowtime(),
			"voucher_type": "Stock Entry",
			"voucher_no": stock_entry.name,
			"voucher_detail_no": stock_entry.items[0].name,
			"actual_qty": -1,
			"stock_uom": "Nos",
			"company": company,
			"batch_no": batch.name,
			"serial_no": serial_no.name
		})
		sle.insert(ignore_permissions=True)

		repost_item_valuation = frappe.get_doc({
			"doctype": "Repost Item Valuation",
			"posting_date": frappe.utils.nowdate(),
			"based_on": "Transaction",
			"voucher_type": "Stock Entry",  
			"voucher_no": stock_entry.name,
			"company": company
		})
		repost_item_valuation.insert()
		repost_item_valuation.submit()
		repost_item_valuation.reload()
		stock_reposting_setting.reload()
		frappe.db.set_value("Repost Item Valuation", repost_item_valuation.name, "status", "Queued")
		stock_reposting_setting.convert_to_item_wh_reposting()
		assert repost_item_valuation.docstatus == 1, "Repost Item Valuation should be submitted"
		assert stock_reposting_setting.item_based_reposting == 1


	def test_notify_reposting_error_to_role(self):
		role = "Notify Reposting Role"

		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role}).insert(ignore_permissions=True)

		user = "notify_reposting_error@test.com"
		if not frappe.db.exists("User", user):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": user,
					"first_name": "Test",
					"language": "en",
					"time_zone": "Asia/Kolkata",
					"send_welcome_email": 0,
					"roles": [{"role": role}],
				}
			).insert(ignore_permissions=True)

		frappe.db.set_single_value("Stock Reposting Settings", "notify_reposting_error_to_role", "")

		users = get_recipients()
		self.assertFalse(user in users)

		frappe.db.set_single_value("Stock Reposting Settings", "notify_reposting_error_to_role", role)

		users = get_recipients()
		self.assertTrue(user in users)

	def test_do_reposting_for_each_stock_transaction(self):
		from erpnext.stock.doctype.item.test_item import make_item
		from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry

		frappe.db.set_single_value("Stock Reposting Settings", "do_reposting_for_each_stock_transaction", 1)
		if frappe.db.get_single_value("Stock Reposting Settings", "item_based_reposting"):
			frappe.db.set_single_value("Stock Reposting Settings", "item_based_reposting", 0)

		item = make_item(
			"_Test item for reposting check for each transaction", properties={"is_stock_item": 1}
		).name

		stock_entry = make_stock_entry(
			item_code=item,
			qty=1,
			rate=100,
			stock_entry_type="Material Receipt",
			target="_Test Warehouse - _TC",
		)

		riv = frappe.get_all("Repost Item Valuation", filters={"voucher_no": stock_entry.name}, pluck="name")
		self.assertTrue(riv)

		frappe.db.set_single_value("Stock Reposting Settings", "do_reposting_for_each_stock_transaction", 0)

	def test_do_not_reposting_for_each_stock_transaction(self):
		from erpnext.stock.doctype.item.test_item import make_item
		from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry

		frappe.db.set_single_value("Stock Reposting Settings", "do_reposting_for_each_stock_transaction", 0)
		if frappe.db.get_single_value("Stock Reposting Settings", "item_based_reposting"):
			frappe.db.set_single_value("Stock Reposting Settings", "item_based_reposting", 0)

		item = make_item(
			"_Test item for do not reposting check for each transaction", properties={"is_stock_item": 1}
		).name

		stock_entry = make_stock_entry(
			item_code=item,
			qty=1,
			rate=100,
			stock_entry_type="Material Receipt",
			target="_Test Warehouse - _TC",
		)

		riv = frappe.get_all("Repost Item Valuation", filters={"voucher_no": stock_entry.name}, pluck="name")
		self.assertFalse(riv)
