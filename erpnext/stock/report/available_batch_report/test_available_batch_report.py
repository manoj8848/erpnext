import frappe
from frappe.tests.utils import FrappeTestCase
from erpnext.stock.report.available_batch_report import available_batch_report
from types import SimpleNamespace
from erpnext.stock.doctype.stock_entry.test_stock_entry import get_or_create_fiscal_year
from erpnext.accounts.doctype.payment_entry.test_payment_entry import create_company
from erpnext.stock.doctype.item.test_item import create_item
from erpnext.stock.doctype.warehouse.test_warehouse import create_warehouse
from frappe.utils import today


class TestAvailableBatchReport(FrappeTestCase):
	def setUp(self):
		self.company = create_company("_Test Company")
		get_or_create_fiscal_year("_Test Company")

		self.warehouse = create_warehouse(warehouse_name = "Stores - W - _TC", company = "_Test Company")
		self.item = create_item(item_code = "TEST-ITEM-100",valuation_rate=100, warehouse = "Stores - W - _TC", company = "_Test Company",has_batch_no =1)

		self.batch = create_batch("BATCH-001", self.item, self.warehouse)
		create_stock_entry(self.item, self.warehouse, self.batch, 100)

	def make_filters(self, **overrides):
		default_filters = dict(
			warehouse=None,
			item_code=None,
			from_date=None,
			to_date=None,
			include_expired_batches=None,
			show_item_name=None,
			batch_no=None,
			warehouse_type=None,
		)
		default_filters.update(overrides)
		return SimpleNamespace(**default_filters)

	# def test_valid_batch_is_returned(self):
	# 	filters = self.make_filters(item_code=self.item.name)
	# 	data = available_batch_report.get_data(filters)
	# 	self.assertGreater(len(data), 0)
	# 	self.assertEqual(data[0].item_code, self.item.name)

	def test_non_existent_item_returns_empty(self):
		filters = self.make_filters(item_code="NON-EXISTENT-ITEM")
		data = available_batch_report.get_data(filters)
		self.assertEqual(len(data), 0)

	def test_filter_by_batch_no(self):
		filters = self.make_filters(batch_no=self.batch.name)
		data = available_batch_report.get_data(filters)
		self.assertTrue(all(d.batch_no == self.batch.name for d in data))

	def test_filter_by_warehouse(self):
		filters = self.make_filters(warehouse=self.warehouse)
		data = available_batch_report.get_data(filters)
		self.assertTrue(all(d.warehouse == self.warehouse for d in data))

	def test_execute_function_returns_data(self):
		filters = self.make_filters(
			item_code=self.item.name,
			warehouse=self.warehouse,
			batch_no=self.batch.name,
			to_date=today()
		)
		columns, data = available_batch_report.execute(filters)
		self.assertGreater(len(data), 0)
		self.assertIn("item_code", data[0])

	def test_execute_includes_item_name_column_based_on_filter(self):
		filters_with_name = self.make_filters(show_item_name=True)
		columns, data = available_batch_report.execute(filters_with_name)
		fieldnames = [col["fieldname"] for col in columns]
		self.assertIn("item_name", fieldnames, "Item Name column should be included when show_item_name=True")


		filters_without_name = self.make_filters(show_item_name=False)
		columns, data = available_batch_report.execute(filters_without_name)
		fieldnames = [col["fieldname"] for col in columns]
		self.assertNotIn("item_name", fieldnames, "Item Name column should NOT be included when show_item_name=False")

	def test_include_expired_batches(self):
		self.batch.expiry_date = "2000-01-01"
		self.batch.reload()
		self.batch.save()
		filters = self.make_filters(item_code=self.item.name, include_expired_batches=True, to_date=today())
		data = available_batch_report.get_data(filters)
		self.assertTrue(any(d.batch_no == self.batch.name for d in data))




def create_batch(batch_name, item, warehouse):
	if not frappe.db.exists("Batch", batch_name):
		return frappe.get_doc({
			"doctype": "Batch",
			"batch_id": batch_name,
			"item": item.name,
			"warehouse": warehouse
		}).insert()
	return frappe.get_doc("Batch", batch_name)

def create_stock_entry(item, warehouse, batch, qty):
	from frappe.utils import nowdate
	entry = frappe.get_doc({
		"doctype": "Stock Entry",
		"stock_entry_type": "Material Receipt",
		"company": "_Test Company",
		"posting_date": nowdate(),
		"items": [{
			"item_code": item.name,
			"qty": qty,
			"t_warehouse": warehouse,
			"batch_no": batch.name
		}]
	})
	entry.insert()
	entry.submit()

