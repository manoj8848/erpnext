import unittest
import frappe
from frappe import _dict
from frappe.utils import nowdate
from erpnext.stock.report.item_variant_details.item_variant_details import execute
from erpnext.stock.doctype.item.test_item import create_item
from erpnext.stock.doctype.stock_entry.test_stock_entry import make_stock_entry
from erpnext.selling.doctype.sales_order.test_sales_order import make_sales_order


def create_test_attribute(attribute_name, values):
    # Unique names like "Size IVS", etc.
    if frappe.db.exists("Item Attribute", attribute_name):
        return

    doc = frappe.get_doc({
        "doctype": "Item Attribute",
        "attribute_name": attribute_name,
        "numeric_values": 0,
        "item_attribute_values": [
            {"attribute_value": val, "abbr": val[0].upper()} for val in values
        ],
    })
    doc.insert()



def create_gst_hsn_code():
	gst_hsn_code = "11112222"
	if not frappe.db.exists("GST HSN Code", gst_hsn_code):
		gst_hsn_code = frappe.new_doc("GST HSN Code")
		gst_hsn_code.hsn_code = "11112222"
		gst_hsn_code.save()
		gst_hsn_code = gst_hsn_code.hsn_code
	else:
		gst_hsn_code = gst_hsn_code
	return gst_hsn_code




class TestItemVariantSummary(unittest.TestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		for attr in ["Size IVS", "Color IVS"]:
			if frappe.db.exists("Item Attribute", attr):
				frappe.delete_doc("Item Attribute", attr, force=1)
		create_test_attribute("Size IVS", ["S", "M"])
		create_test_attribute("Color IVS", ["Red", "Blue"])
		if not frappe.db.exists("Item", "Test Parent IVS"):
			self.item = frappe.get_doc({
                "doctype": "Item",
                "item_code": "Test Parent IVS",
                "item_name": "Test Parent IVS",
                "item_group": "All Item Groups",
                "stock_uom": "Nos",
                "is_stock_item": 1,
                "has_variants": 1,
                "gst_hsn_code": create_gst_hsn_code(),
                "variant_based_on": "Item Attribute",
                "attributes": [
                    {"attribute": "Size IVS"},
                    {"attribute": "Color IVS"},
                ]
            }).insert()
		else:
			self.item = frappe.get_doc("Item", "Test Parent IVS")
		self.item_nonvariant = create_item("Test Item No Variants IVS", {
            "is_stock_item": 1,
            "stock_uom": "Nos"
        })
		if not frappe.db.exists("Item", "Test Variant 1 IVS"):
			self.variant_1 = frappe.get_doc({
            "doctype": "Item",
            "item_code": "Test Variant 1 IVS",
            "item_name": "Test Variant 1",
				"item_group": "All Item Groups",
            "variant_of": self.item.name,
			"gst_hsn_code": create_gst_hsn_code(),
            "is_stock_item": 1,
            "attributes": [
                {"attribute": "Size IVS", "attribute_value": "S"},
                {"attribute": "Color IVS", "attribute_value": "Red"},
            ],
            }).insert()
		else:
			self.variant_1 = frappe.get_doc("Item", "Test Variant 1 IVS")
		if not frappe.db.exists("Item", "Test Variant 2 IVS"):
			self.variant_2 = frappe.get_doc({
            "doctype": "Item",
            "item_code": "Test Variant 2 IVS",
            "item_name": "Test Variant 2",
				"item_group": "All Item Groups",
			"gst_hsn_code": create_gst_hsn_code(),
            "variant_of": self.item.name,
            "is_stock_item": 1,
            "attributes": [
                {"attribute": "Size IVS", "attribute_value": "M"},
                {"attribute": "Color IVS", "attribute_value": "Blue"},
            ],
            }).insert()
		else:
			self.variant_2 = frappe.get_doc("Item", "Test Variant 2 IVS")


	def test_no_item_filter_T_IVS_001(self):
		"""T_IVS_001: Report should return error if item filter is not passed"""
		with self.assertRaises(Exception) as context:
			execute(filters=_dict({}))
		self.assertIn("Item None not found", str(context.exception))

	def test_item_without_variants_T_IVS_002(self):
		"""T_IVS_002: Report should return empty data for non-variant items"""
		columns, data = execute(filters=_dict({"item": self.item_nonvariant.name}))
		self.assertEqual(data, [])

	def test_item_with_variants_T_IVS_003(self):
		"""T_IVS_003: Report should return correct columns and data for variant item"""
		columns, data = execute(filters=_dict({"item": self.item.name}))
		self.assertGreater(len(data), 0)
		variant = data[0]
		self.assertIn("variant_name", variant)
		self.assertIn("current_stock", variant)
		self.assertIn("avg_buying_price_list_rate", variant)
		self.assertIn("open_orders", variant)

	def test_item_variant_report_T_IVS_004(self):
		"""T_IVS_004: All defined variant values should appear in the report"""
		columns, data = execute(filters=_dict({"item": self.item.name}))
		self.assertGreater(len(data), 0)
		variant_names = [d.get("variant_name") for d in data]
		self.assertIn(self.variant_1.name, variant_names)
		self.assertIn(self.variant_2.name, variant_names)
		for row in data:
			self.assertIn("avg_buying_price_list_rate", row)
			self.assertIn("avg_selling_price_list_rate", row)
			self.assertIn("current_stock", row)
			self.assertIn("open_orders", row)
