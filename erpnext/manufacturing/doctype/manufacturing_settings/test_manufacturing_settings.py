# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt
import frappe
import unittest
from erpnext.manufacturing.doctype.manufacturing_settings.manufacturing_settings import ManufacturingSettings
from erpnext.stock.doctype.warehouse.test_warehouse import create_warehouse

class TestManufacturingSettings(unittest.TestCase):
	def test_manufacturing_settings_TC_SCK_220(self):
		company = "_Test Company"
		create_warehouse("_Test WIP Warehouse", company=company)
		create_warehouse("_Test Scrap Warehouse", company=company)
		create_warehouse("_Test Finished Goods Warehouse", company=company)
		settings = frappe.get_doc({
			"doctype": "Manufacturing Settings",
			"default_wip_warehouse": "_Test WIP Warehouse - _TC",
			"default_scrap_warehouse": "_Test Scrap Warehouse - _TC",
			"default_fg_warehouse": "_Test Finished Goods Warehouse - _TC",
		})
		settings.insert()

		self.assertEqual(settings.default_wip_warehouse, "_Test WIP Warehouse - _TC")
		self.assertEqual(settings.default_scrap_warehouse, "_Test Scrap Warehouse - _TC")
		self.assertEqual(settings.default_fg_warehouse, "_Test Finished Goods Warehouse - _TC")

	def test_overproduction_percentage_for_work_order_TC_SCK_221(self):
		# Set up the overproduction percentage for work orders
		settings = frappe.get_doc({
			"doctype": "Manufacturing Settings",
			"overproduction_percentage_for_work_order": 10
		})
		settings.insert()

		# Verify the overproduction percentage is set correctly
		self.assertEqual(settings.overproduction_percentage_for_work_order, 10)
		
	def test_overproduction_percentage_for_sales_order_TC_SCK_222(self):
		# Set up the overproduction percentage for sales orders
		settings = frappe.get_doc({
			"doctype": "Manufacturing Settings",
			"overproduction_percentage_for_sales_order": 15
		})
		settings.insert()

		# Verify the overproduction percentage is set correctly
		self.assertEqual(settings.overproduction_percentage_for_sales_order, 15)
	