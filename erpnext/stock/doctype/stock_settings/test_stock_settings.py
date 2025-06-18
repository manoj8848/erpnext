# Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt


import frappe
from frappe.tests.utils import FrappeTestCase, change_settings, if_app_installed


class TestStockSettings(FrappeTestCase):
	def setUp(self):
		super().setUp()
		frappe.db.set_single_value("Stock Settings", "clean_description_html", 0)

	def tearDown(self):
		frappe.db.rollback()

	# codecov
	def test_cant_change_valuation_method_TC_SCK_326(self):
		settings = frappe.get_doc("Stock Settings")
		settings.valuation_method = "FIFO"

		settings.valuation_method = "Moving Average"
		msg = "Can't change the valuation method, as there are transactions against some items which do not have its own valuation method"
		with self.assertRaises(frappe.ValidationError, msg=msg):
			settings.save()

	# codecov
	@change_settings("Stock Settings", {"allow_negative_stock": 0, "enable_stock_reservation": 1})
	def test_validate_stock_reservation_TC_SCK_335(self):
		frappe.flags.in_test = False  # Force validation to run

		settings = frappe.get_doc("Stock Settings")
		settings.allow_negative_stock = 1  # Trying to enable it while stock reservation is ON

		msg = "As Stock Reservation is enabled, you can not enable Allow Negative Stock."
		with self.assertRaises(frappe.ValidationError, msg=msg):
			settings.save()

		frappe.flags.in_test = True  # Reset for other tests

	# codecov
	@change_settings("Stock Settings", {"allow_negative_stock": 1, "enable_stock_reservation": 0})
	def test_validate_stock_reservation_TC_SCK_336(self):
		frappe.flags.in_test = False  # Force validation to run

		settings = frappe.get_doc("Stock Settings")
		settings.enable_stock_reservation = 1  # Trying to enable it
		# allow_negative_stock is already 1 from change_settings
		msg = "As Allow Negative Stock is enabled, you can not enable Stock Reservation."
		with self.assertRaises(frappe.ValidationError, msg=msg):
			settings.save()

		frappe.flags.in_test = True  # Reset after test

	# codecov
	@change_settings("Stock Settings", {"allow_negative_stock": 1, "enable_stock_reservation": 0})
	def test_validate_stock_reservation_TC_SCK_337(self):
		from frappe.query_builder.functions import Round

		frappe.flags.in_test = False  # Force validation to run

		settings = frappe.get_doc("Stock Settings")
		settings.enable_stock_reservation = 1  # Trying to enable it
		settings.allow_negative_stock = 0
		msg = "As there are negative stock, you can not enable Stock Reservation."
		precision = frappe.db.get_single_value("System Settings", "float_precision") or 3
		bin = frappe.qb.DocType("Bin")
		bin_with_negative_stock = (
			frappe.qb.from_(bin).select(bin.name).where(Round(bin.actual_qty, precision) < 0).limit(1)
		).run()
		if bin_with_negative_stock:
			msg = "As there are negative stock, you can not enable Stock Reservation."
			with self.assertRaises(frappe.ValidationError, msg=msg):
				settings.save()
		else:
			# In case there's no negative stock, it should save successfully
			settings.save()
			self.assertEqual(settings.enable_stock_reservation, 1)

	# codecov
	@change_settings("Stock Settings", {"allow_negative_stock": 1, "enable_stock_reservation": 1})
	def test_validate_stock_reservation_TC_SCK_338(self):
		frappe.flags.in_test = False  # Force validation to run

		settings = frappe.get_doc("Stock Settings")
		settings.enable_stock_reservation = 0  # Trying to enable it
		settings.allow_negative_stock = 0

		msg = "As there are reserved stock, you cannot disable Stock Reservation."
		with self.assertRaises(frappe.ValidationError, msg=msg):
			settings.save()
		self.assertEqual(settings.allow_negative_stock, 0)

	# codecov
	@change_settings(
		"Stock Settings",
		{
			"allow_negative_stock": 0,
			"enable_stock_reservation": 1,
			"allow_to_edit_stock_uom_qty_for_sales": 0,
		},
	)
	def test_validate_stock_reservation_TC_SCK_339(self):
		frappe.flags.in_test = False  # Force validation to run

		# Fetch doc from DB (with previous value 0)

		settings = frappe.get_doc("Stock Settings")

		# Now change the field to 1 → this triggers the print
		settings.allow_to_edit_stock_uom_qty_for_sales = 1
		settings.save()  # Should now enter your condition and print line
		self.assertEqual(settings.allow_to_edit_stock_uom_qty_for_sales, 1)
		frappe.flags.in_test = True  # Reset

	# codecov
	@change_settings(
		"Stock Settings",
		{
			"allow_negative_stock": 1,
			"enable_stock_reservation": 1,
			"allow_to_edit_stock_uom_qty_for_sales": 0,
		},
	)
	def test_change_precision_for_for_sales_TC_SCK_340(self):
		frappe.flags.in_test = False  # Force validation

		settings = frappe.get_doc("Stock Settings")
		settings.allow_to_edit_stock_uom_qty_for_sales = 1  # Changing from 0 → 1

		settings.save()  # This should call `validate` -> `change_precision_for_for_sales`
		self.assertEqual(settings.allow_to_edit_stock_uom_qty_for_sales, 1)
		frappe.flags.in_test = True

	# codecov
	@change_settings(
		"Stock Settings",
		{
			"allow_negative_stock": 1,
			"enable_stock_reservation": 1,
			"allow_to_edit_stock_uom_qty_for_sales": 0,
			"allow_to_edit_stock_uom_qty_for_purchase": 1,
		},
	)
	def test_change_precision_for_for_purchase_TC_SCK_341(self):
		frappe.flags.in_test = False  # Force validation

		settings = frappe.get_doc("Stock Settings")
		settings.allow_to_edit_stock_uom_qty_for_purchase = 1  # Changing from 0 → 1

		settings.save()  # This should call `validate` -> `change_precision_for_for_sales`
		self.assertEqual(settings.allow_to_edit_stock_uom_qty_for_purchase, 1)
		frappe.flags.in_test = True

	# codecov
	@change_settings(
		"Stock Settings",
		{
			"allow_negative_stock": 1,
			"enable_stock_reservation": 1,
			"allow_to_edit_stock_uom_qty_for_sales": 0,
			"allow_to_edit_stock_uom_qty_for_purchase": 1,
		},
	)
	def test_get_enable_stock_uom_editing_TC_SCK_342(self):
		from erpnext.stock.doctype.stock_settings.stock_settings import get_enable_stock_uom_editing

		frappe.flags.in_test = False  # Force validation

		settings = frappe.get_doc("Stock Settings")
		settings.allow_to_edit_stock_uom_qty_for_purchase = 1
		settings.save()

		result = get_enable_stock_uom_editing()

		frappe.flags.in_test = True

		assert result["allow_to_edit_stock_uom_qty_for_purchase"] == 1
		assert result["allow_to_edit_stock_uom_qty_for_sales"] == 0

	def test_settings(self):
		item = frappe.get_doc(
			dict(
				doctype="Item",
				item_code="Item for description test",
				item_group="Products",
				description='<p><span style="font-size: 12px;">Drawing No. 07-xxx-PO132<br></span><span style="font-size: 12px;">1800 x 1685 x 750<br></span><span style="font-size: 12px;">All parts made of Marine Ply<br></span><span style="font-size: 12px;">Top w/ Corian dd<br></span><span style="font-size: 12px;">CO, CS, VIP Day Cabin</span></p>',
			)
		).insert()

		settings = frappe.get_single("Stock Settings")
		settings.clean_description_html = 1
		settings.save()

		item.reload()

		self.assertEqual(
			item.description,
			"<p>Drawing No. 07-xxx-PO132<br>1800 x 1685 x 750<br>All parts made of Marine Ply<br>Top w/ Corian dd<br>CO, CS, VIP Day Cabin</p>",
		)

		item.delete()

	def test_clean_html(self):
		settings = frappe.get_single("Stock Settings")
		settings.clean_description_html = 1
		settings.save()

		item = frappe.get_doc(
			dict(
				doctype="Item",
				item_code="Item for description test",
				item_group="Products",
				description='<p><span style="font-size: 12px;">Drawing No. 07-xxx-PO132<br></span><span style="font-size: 12px;">1800 x 1685 x 750<br></span><span style="font-size: 12px;">All parts made of Marine Ply<br></span><span style="font-size: 12px;">Top w/ Corian dd<br></span><span style="font-size: 12px;">CO, CS, VIP Day Cabin</span></p>',
			)
		).insert()

		self.assertEqual(
			item.description,
			"<p>Drawing No. 07-xxx-PO132<br>1800 x 1685 x 750<br>All parts made of Marine Ply<br>Top w/ Corian dd<br>CO, CS, VIP Day Cabin</p>",
		)

		item.delete()
