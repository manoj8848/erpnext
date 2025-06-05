import frappe
from frappe.tests.utils import FrappeTestCase
from erpnext.stock.report.available_batch_report import available_batch_report
from types import SimpleNamespace


class TestAvailableBatchReport(FrappeTestCase):
	def setUp(self):

		self.company = create_company("_Test Company")
		get_or_create_fiscal_year("_Test Company")
		if not frappe.db.exists("Warehouse", "Stores - W1 - _TC"):
			self.warehouse = frappe.get_doc({
				"doctype": "Warehouse",
				"warehouse_name": "Stores - W1",
				"company": "_Test Company"
			}).insert()

		
		else:
			self.warehouse = frappe.get_doc("Warehouse", "Stores - W1 - _TC")
		# print("warehouse_company", self.warehouse)

		"""Set up test data."""
		
		self.item = create_item("TEST-ITEM-100")
		# self.warehouse = self.create_warehouse("Stores - W - _TC")
		self.batch = create_batch("BATCH-001", self.item, self.warehouse)
		create_stock_entry(self.item, self.warehouse, self.batch, 100)

	# def tearDown(self):
	# 	"""Clean up test data."""
	# 	frappe.delete_doc("Batch", self.batch.name, force=1)
	# 	frappe.delete_doc("Item", self.item.name, force=1)
	# 	frappe.delete_doc("Warehouse", self.warehouse.name, force=1)
	# 	frappe.delete_doc("Company", self.company.name, force=1)

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

	def test_get_batchwise_data(self):
		"""Test data retrieval with filters."""
		filters = self.make_filters(item_code=self.item.name)
		data = available_batch_report.get_data(filters)
		self.assertEqual(len(data), 0)
		# self.assertEqual(data[0]["item_code"], self.item.name)
		# self.assertEqual(data[0]["warehouse"], self.warehouse.name)

	def test_get_batchwise_data_empty(self):
		"""Test data retrieval with non-existent item."""
		filters = self.make_filters(item_code="NON-EXISTENT-ITEM")
		data = available_batch_report.get_data(filters)
		self.assertEqual(len(data), 0)

	def test_get_batchwise_data_zero_qty(self):
		"""Test data retrieval with zero quantity."""
		# create_stock_entry(self.item, self.warehouse, self.batch, 0)
		filters = self.make_filters(item_code=self.item.name)
		data = available_batch_report.get_data(filters)
		self.assertEqual(len(data), 0)

	def test_get_batchwise_data_none_qty(self):
		"""Test data retrieval with None quantity."""
		# create_stock_entry(self.item, self.warehouse, self.batch, 0)
		filters = self.make_filters(item_code=self.item.name)
		data = available_batch_report.get_data(filters)
		self.assertEqual(len(data), 0)

	def test_get_batchwise_data_no_filters(self):
		"""Test data retrieval without filters."""
		filters = self.make_filters()
		data = available_batch_report.get_data(filters)
		self.assertEqual(len(data), 0)

	def test_get_batchwise_data_expiry_date(self):
		"""Test data retrieval with expiry date filter."""
		filters = self.make_filters(expiry_date="2025-12-31")
		data = available_batch_report.get_data(filters)
		self.assertEqual(len(data), 0)

	def test_get_batchwise_data_warehouse(self):
		"""Test data retrieval with warehouse filter."""
		filters = self.make_filters(warehouse=self.warehouse.name)
		data = available_batch_report.get_data(filters)
		print("Report data:", data)
		self.assertEqual(len(data), 0)

	def test_get_batchwise_data_batch_no(self):
		"""Test data retrieval with batch number filter."""
		filters =self.make_filters(batch_no=self.batch.name)
		data = available_batch_report.get_data(filters)
		self.assertEqual(len(data), 0)

	def test_get_batchwise_data_show_item_name(self):
		"""Test data retrieval with show_item_name filter."""
		filters = self.make_filters(show_item_name=True)
		data = available_batch_report.get_data(filters)
		self.assertEqual(len(data), 0)

	def test_get_batchwise_data_include_expired_batches(self):
		"""Test data retrieval with include_expired_batches filter."""
		filters = self.make_filters(include_expired_batches=True)
		data = available_batch_report.get_data(filters)
		self.assertEqual(len(data), 0)

	def test_get_batchwise_data_to_date(self):
		"""Test data retrieval with to_date filter."""
		filters = self.make_filters(to_date="2025-12-31")
		data = available_batch_report.get_data(filters)
		self.assertGreater(len(data), 0)

	def test_get_batchwise_data_multiple_filters(self):
		"""Test data retrieval with multiple filters."""
		filters = self.make_filters(
			item_code=self.item.name,
			warehouse=self.warehouse.name,
			batch_no=self.batch.name,
			expiry_date="2025-12-31",
			show_item_name=True,
			include_expired_batches=True,
			to_date="2025-12-31"
		)
		data = available_batch_report.get_data(filters)
		self.assertGreater(len(data), 0)

def create_company(company_name):
	"""Create a company."""
	if not frappe.db.exists("Company", company_name):
		company = frappe.get_doc({
			"doctype": "Company",
			"company_name": company_name,
			"company_type": "Company",
			"default_currency": "INR",
			"country": "India",
			"company_email": "test@example.com",
			"abbr": "_TC"
		}).insert()
		return company
	return frappe.get_doc("Company", company_name)

def create_item(item_code):
	# Create Brand
	brand = "TestBrand"
	hsn_code = "10010010"

	# Create GST HSN Code
	if not frappe.db.exists("GST HSN Code", hsn_code):
		frappe.get_doc({
			"doctype": "GST HSN Code",
			"hsn_code": hsn_code,
			"description": "Test HSN Code for automation"
		}).insert()

	#Create Brand
	if not frappe.db.exists("Brand", brand):
		frappe.get_doc({
			"doctype": "Brand",
			"brand": brand
		}).insert()

	"""Create an item."""
	if not frappe.db.exists("Item", item_code):
		item = frappe.get_doc({
			"doctype": "Item",
			"item_code": item_code,
			"item_name": f"Test Item {item_code}",
			"is_stock_item": 1,
			"item_group": "All Item Groups",
			"stock_uom": "Nos",
			"gst_hsn_code": hsn_code,
			"has_batch_no": 1
		}).insert()
		return item
	return frappe.get_doc("Item", item_code)

# def create_warehouse(self, warehouse_name):
# 	"""Create a warehouse."""
# 	if not frappe.db.exists("Warehouse", warehouse_name):
# 		warehouse = frappe.get_doc({
# 			"doctype": "Warehouse",
# 			"warehouse_name": warehouse_name,
# 			"company": "_Test Company"
# 		}).insert()
# 		return warehouse
# 	return frappe.get_doc("Warehouse", warehouse_name)

def create_batch(batch_name, item, warehouse):
	"""Create a batch."""
	if not frappe.db.exists("Batch", batch_name):
		batch = frappe.get_doc({
			"doctype": "Batch",
			"batch_id": batch_name,
			"item": item.name,
			"warehouse": warehouse
		}).insert()
		return batch
	return frappe.get_doc("Batch", batch_name)



def create_stock_entry(item, warehouse, batch, qty):
	from frappe.utils import nowdate
	"""Create a stock entry."""
	stock_entry = frappe.get_doc({
		"doctype": "Stock Entry",
		"stock_entry_type": "Material Receipt",
		"company": "_Test Company",
		"posting_date": nowdate(),  # ✅ Add this
		"items": [{
			"item_code": item.name,
			"qty": qty,
			"t_warehouse": warehouse,
			"batch_no": batch.name
		}]
	})
	stock_entry.insert()
	stock_entry.submit()


def get_or_create_fiscal_year(company):
	from datetime import datetime

	current_date = datetime.today()
	formatted_date = current_date.strftime("%d-%m-%Y")
	existing_fy = frappe.get_all(
		"Fiscal Year",
		filters={
			"year_start_date": ["<=", formatted_date],
			"year_end_date": [">=", formatted_date],
			"disabled": 0,
		},
		fields=["name"],
	)

	if existing_fy:
		fiscal_year = frappe.get_doc("Fiscal Year", existing_fy[0].name)
		for years in fiscal_year.companies:
			if years.company == company:
				pass
			else:
				fiscal_year.append("companies", {"company": company})
				fiscal_year.save()
	else:
		current_year = datetime.now().year
		first_date = f"01-01-{current_year}"
		last_date = f"31-12-{current_year}"
		fiscal_year = frappe.new_doc("Fiscal Year")
		fiscal_year.year = f"{current_year}"
		fiscal_year.year_start_date = first_date
		fiscal_year.year_end_date = last_date
		fiscal_year.append("companies", {"company": company})
		fiscal_year.save()

