# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt


import unittest

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import random_string

# test_ignore = ["Item"]

test_records = frappe.get_test_records("Price List")


class TestPriceList(FrappeTestCase):
	def setUp(self):
		# Generate unique names for price lists
		self.buying_price_list_name = f"Buying-{random_string(5)}"
		self.selling_price_list_name = f"Selling-{random_string(5)}"

	# codecov
	def test_validate_price_list_TC_SCK_327(self):
		price_list = frappe.get_doc(
			{"doctype": "Price List", "price_list_name": "Test Price list", "buying": 0, "selling": 0}
		)

		msg = "Price List must be applicable for Buying or Selling"
		with self.assertRaises(frappe.ValidationError, msg=msg):
			price_list.insert()

	# codecov
	def test_get_price_list_details_TC_SCK_328(self):
		from erpnext.stock.doctype.price_list.price_list import get_price_list_details

		if not frappe.db.exists("Price List", "Test Price List1"):
			frappe.get_doc(
				{
					"doctype": "Price List",
					"price_list_name": "Test Price List1",
					"buying": 1,
					"selling": 1,
					"enabled": 0,
				}
			).insert()

			msg = "Price List Test Price List1 is disabled or does not exist"
			with self.assertRaises(frappe.ValidationError, msg=msg):
				get_price_list_details("Test Price List1")

	def test_buying_price_list(self):
		# Create Buying Price List
		buying_price_list = frappe.get_doc(
			{
				"doctype": "Price List",
				"price_list_name": self.buying_price_list_name,
				"buying": 1,
				"selling": 0,
			}
		).insert()
		buying_price_list.reload()
		buying_price_list.delete()

		# Verify in Purchase Order
		price_lists = [pl.name for pl in frappe.get_all("Price List", fields=["name"], filters={"buying": 1})]
		self.assertIn(
			buying_price_list.name, price_lists, "Buying Price List not available in Purchase Order"
		)

		# Verify not available in Sales Order
		price_lists = [
			pl.name for pl in frappe.get_all("Price List", fields=["name"], filters={"selling": 1})
		]
		self.assertNotIn(
			buying_price_list.name, price_lists, "Buying Price List should not be available in Sales Order"
		)

	def test_selling_price_list(self):
		# Create Selling Price List
		selling_price_list = frappe.get_doc(
			{
				"doctype": "Price List",
				"price_list_name": self.selling_price_list_name,
				"buying": 0,
				"selling": 1,
			}
		).insert()

		# Verify in Sales Order
		price_lists = [
			pl.name
			for pl in frappe.get_all("Price List", fields=["name"], filters={"selling": 1, "buying": 0})
		]
		self.assertIn(selling_price_list.name, price_lists, "Selling Price List not available in Sales Order")

		# Verify not available in Purchase Order
		price_lists = [
			pl.name
			for pl in frappe.get_all("Price List", fields=["name"], filters={"buying": 1, "selling": 0})
		]
		self.assertNotIn(
			selling_price_list.name,
			price_lists,
			"Selling Price List should not be available in Purchase Order",
		)

	def tearDown(self):
		# Cleanup created price lists
		if frappe.db.exists("Price List", self.buying_price_list_name):
			frappe.delete_doc("Price List", self.buying_price_list_name)
		if frappe.db.exists("Price List", self.selling_price_list_name):
			frappe.delete_doc("Price List", self.selling_price_list_name)
