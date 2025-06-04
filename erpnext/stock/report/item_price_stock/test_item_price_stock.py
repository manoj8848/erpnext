import frappe
from frappe.tests.utils import FrappeTestCase
from erpnext.stock.report.item_price_stock import item_price_stock

class TestItemPriceReport(FrappeTestCase):
	def setUp(self):
		self.buying_pl = get_or_create_price_list("Test Buying PL", buying=1, selling=0)
		self.selling_pl = get_or_create_price_list("Test Selling PL", buying=0, selling=1)

		self.item = get_or_create_item("TEST-ITEM-100")

		self.buying_price = get_or_create_item_price(
			item_code=self.item.name,
			price_list=self.buying_pl.name,
			price_list_rate=50,
			buying=1,
			selling=0
		)

		self.selling_price = get_or_create_item_price(
			item_code=self.item.name,
			price_list=self.selling_pl.name,
			price_list_rate=80,
			buying=0,
			selling=1
		)

		if not frappe.db.exists("Company", "_Test Company"):
			frappe.get_doc({
				"doctype": "Company",
				"company_name": "_Test Company",
				"company_type": "Company",
				"default_currency": "INR",
				"country": "India",
				"company_email": "test@example.com",
				"abbr": "_TC"
			}).insert()

		if not frappe.db.exists("Warehouse", "Stores - W - _TC"):
			frappe.get_doc({
				"doctype": "Warehouse",
				"warehouse_name": "Stores - W - _TC",
				"company": "_Test Company"
			}).insert()

		self.bin = get_or_create_bin(self.item.name, "Stores - W - _TC", 15)


	def tearDown(self):
		# Delete in reverse order
		frappe.delete_doc("Bin", self.bin.name, force=1)
		frappe.delete_doc("Item Price", self.buying_price.name, force=1)
		frappe.delete_doc("Item Price", self.selling_price.name, force=1)
		frappe.delete_doc("Item", self.item.name, force=1)
		frappe.delete_doc("Price List", self.buying_pl.name, force=1)
		frappe.delete_doc("Price List", self.selling_pl.name, force=1)

	def test_get_columns(self):
		columns = item_price_stock.get_columns()
		self.assertIsInstance(columns, list)
		self.assertTrue(any(col["fieldname"] == "item_code" for col in columns))

	def test_get_price_map_buying(self):
		price_map = item_price_stock.get_price_map([self.buying_price.name], buying=1)
		self.assertIn(self.buying_price.name, price_map)
		self.assertEqual(price_map[self.buying_price.name]["Buying Rate"], 50)

	def test_get_price_map_selling(self):
		price_map = item_price_stock.get_price_map([self.selling_price.name], selling=1)
		self.assertIn(self.selling_price.name, price_map)
		self.assertEqual(price_map[self.selling_price.name]["Selling Rate"], 80)

	def test_get_item_price_qty_data(self):
		# Both prices present — ensures both buying and selling price handled
		filters = {"item_code": self.item.name}
		result = item_price_stock.get_item_price_qty_data(filters)
		self.assertTrue(len(result) > 0)
		item_row = result[0]
		self.assertEqual(item_row["item_code"], self.item.name)
		self.assertEqual(item_row["stock_available"], 15)

	def test_get_data(self):
		filters = {"item_code": self.item.name}
		columns = item_price_stock.get_columns()
		data = item_price_stock.get_data(filters, columns)
		self.assertTrue(data)
		self.assertEqual(data[0]["item_code"], self.item.name)

	def test_execute(self):
		filters = {"item_code": self.item.name}
		columns, data = item_price_stock.execute(filters)
		self.assertTrue(columns)
		self.assertTrue(data)
		self.assertEqual(columns[0]["fieldname"], "item_code")
		self.assertEqual(data[0]["item_code"], self.item.name)


def get_or_create_price_list(price_list_name, buying=0, selling=0):
	if frappe.db.exists("Price List", price_list_name):
		return frappe.get_doc("Price List", price_list_name)
	return frappe.get_doc({
		"doctype": "Price List",
		"price_list_name": price_list_name,
		"buying": buying,
		"selling": selling
	}).insert(ignore_permissions=True)

def get_or_create_item(item_code):
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

	if frappe.db.exists("Item", item_code):
		return frappe.get_doc("Item", item_code)
	return frappe.get_doc({
		"doctype": "Item",
		"item_code": item_code,
		"item_name": f"Test Item {item_code}",
		"brand": "TestBrand",
		"is_stock_item": 1,
		"item_group": "All Item Groups",
		"stock_uom": "Nos",
		"gst_hsn_code": hsn_code
	}).insert(ignore_permissions=True)

def get_or_create_item_price(item_code, price_list, price_list_rate, buying=0, selling=0):
	filters = {
		"item_code": item_code,
		"price_list": price_list,
		"buying": buying,
		"selling": selling,
	}
	existing = frappe.get_all("Item Price", filters=filters, limit=1)
	if existing:
		ip = frappe.get_doc("Item Price", existing[0].name)
		if ip.price_list_rate != price_list_rate:
			ip.price_list_rate = price_list_rate
			ip.save(ignore_permissions=True)
		return ip
	else:
		ip = frappe.get_doc({
			"doctype": "Item Price",
			"item_code": item_code,
			"price_list": price_list,
			"price_list_rate": price_list_rate,
			"buying": buying,
			"selling": selling
		}).insert(ignore_permissions=True)
		return ip

def get_or_create_bin(item_code, warehouse, actual_qty):
	filters = {
		"item_code": item_code,
		"warehouse": warehouse
	}
	existing = frappe.get_all("Bin", filters=filters, limit=1)
	if existing:
		bin_doc = frappe.get_doc("Bin", existing[0].name)
		if bin_doc.actual_qty != actual_qty:
			bin_doc.actual_qty = actual_qty
			bin_doc.save(ignore_permissions=True)
		return bin_doc
	else:
		bin_doc = frappe.get_doc({
			"doctype": "Bin",
			"item_code": item_code,
			"warehouse": warehouse,
			"actual_qty": actual_qty
		}).insert(ignore_permissions=True)
		return bin_doc


# Example usage in your test setUp method