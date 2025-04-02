# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase, change_settings
from frappe.utils import nowdate

from erpnext.controllers.stock_controller import (
	QualityInspectionNotSubmittedError,
	QualityInspectionRejectedError,
	QualityInspectionRequiredError,
	make_quality_inspections,
)
from erpnext.stock.doctype.delivery_note.test_delivery_note import create_delivery_note
from erpnext.stock.doctype.item.test_item import create_item
from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry
from erpnext.stock.doctype.purchase_receipt.test_purchase_receipt import make_purchase_receipt
from erpnext.accounts.doctype.purchase_invoice.test_purchase_invoice import make_purchase_invoice
from erpnext.accounts.doctype.sales_invoice.test_sales_invoice import create_sales_invoice
from erpnext.stock.doctype.warehouse.test_warehouse import create_warehouse

# test_records = frappe.get_test_records('Quality Inspection')


class TestQualityInspection(FrappeTestCase):
	def setUp(self):
		from erpnext.accounts.doctype.payment_entry.test_payment_entry import create_company
		create_company()
		create_warehouse(
			warehouse_name="_Test Warehouse - _TC",
			properties={"parent_warehouse": "All Warehouses - _TC"},
			company="_Test Company",
		)
		super().setUp()
		create_item("_Test Item with QA")
		frappe.db.set_value("Item", "_Test Item with QA", "inspection_required_before_delivery", 1)

	def test_qa_for_delivery(self):
		make_stock_entry(
			item_code="_Test Item with QA", target="_Test Warehouse - _TC", qty=1, basic_rate=100
		)
		dn = create_delivery_note(item_code="_Test Item with QA", do_not_submit=True)

		self.assertRaises(QualityInspectionRequiredError, dn.submit)

		qa = create_quality_inspection(
			reference_type="Delivery Note", reference_name=dn.name, status="Rejected"
		)
		dn.reload()
		self.assertRaises(QualityInspectionRejectedError, dn.submit)

		frappe.db.set_value("Quality Inspection", qa.name, "status", "Accepted")
		dn.reload()
		dn.submit()

		qa.reload()
		qa.cancel()
		dn.reload()
		dn.cancel()

	def test_qa_not_submit(self):
		dn = create_delivery_note(item_code="_Test Item with QA", do_not_submit=True)
		qa = create_quality_inspection(
			reference_type="Delivery Note", reference_name=dn.name, do_not_submit=True
		)
		dn.items[0].quality_inspection = qa.name
		self.assertRaises(QualityInspectionNotSubmittedError, dn.submit)

		qa.delete()
		dn.delete()

	def test_value_based_qi_readings(self):
		# Test QI based on acceptance values (Non formula)
		dn = create_delivery_note(item_code="_Test Item with QA", do_not_submit=True)
		readings = [
			{
				"specification": "Iron Content",  # numeric reading
				"min_value": 0.1,
				"max_value": 0.9,
				"reading_1": "0.4",
			},
			{
				"specification": "Particle Inspection Needed",  # non-numeric reading
				"numeric": 0,
				"value": "Yes",
				"reading_value": "Yes",
			},
		]

		qa = create_quality_inspection(
			reference_type="Delivery Note", reference_name=dn.name, readings=readings, do_not_save=True
		)

		qa.save()

		# status must be auto set as per formula
		self.assertEqual(qa.readings[0].status, "Accepted")
		self.assertEqual(qa.readings[1].status, "Accepted")

		qa.delete()
		dn.delete()

	def test_formula_based_qi_readings(self):
		dn = create_delivery_note(item_code="_Test Item with QA", do_not_submit=True)
		readings = [
			{
				"specification": "Iron Content",  # numeric reading
				"formula_based_criteria": 1,
				"acceptance_formula": "reading_1 > 0.35 and reading_1 < 0.50",
				"reading_1": "0.4",
			},
			{
				"specification": "Calcium Content",  # numeric reading
				"formula_based_criteria": 1,
				"acceptance_formula": "reading_1 > 0.20 and reading_1 < 0.50",
				"reading_1": "0.7",
			},
			{
				"specification": "Mg Content",  # numeric reading
				"formula_based_criteria": 1,
				"acceptance_formula": "mean < 0.9",
				"reading_1": "0.5",
				"reading_2": "0.7",
				"reading_3": "random text",  # check if random string input causes issues
			},
			{
				"specification": "Calcium Content",  # non-numeric reading
				"formula_based_criteria": 1,
				"numeric": 0,
				"acceptance_formula": "reading_value in ('Grade A', 'Grade B', 'Grade C')",
				"reading_value": "Grade B",
			},
		]

		qa = create_quality_inspection(
			reference_type="Delivery Note", reference_name=dn.name, readings=readings, do_not_save=True
		)

		qa.save()

		# status must be auto set as per formula
		self.assertEqual(qa.readings[0].status, "Accepted")
		self.assertEqual(qa.readings[1].status, "Rejected")
		self.assertEqual(qa.readings[2].status, "Accepted")
		self.assertEqual(qa.readings[3].status, "Accepted")

		qa.delete()
		dn.delete()

	def test_make_quality_inspections_from_linked_document(self):
		dn = create_delivery_note(item_code="_Test Item with QA", do_not_submit=True)
		for item in dn.items:
			item.sample_size = item.qty
		quality_inspections = make_quality_inspections(dn.doctype, dn.name, dn.items)
		self.assertEqual(len(dn.items), len(quality_inspections))

		# cleanup
		for qi in quality_inspections:
			frappe.delete_doc("Quality Inspection", qi)
		dn.delete()

	def test_rejected_qi_validation(self):
		"""Test if rejected QI blocks Stock Entry as per Stock Settings."""
		se = make_stock_entry(
			item_code="_Test Item with QA",
			target="_Test Warehouse - _TC",
			qty=1,
			basic_rate=100,
			inspection_required=True,
			do_not_submit=True,
		)

		readings = [{"specification": "Iron Content", "min_value": 0.1, "max_value": 0.9, "reading_1": "1.0"}]

		qa = create_quality_inspection(
			reference_type="Stock Entry", reference_name=se.name, readings=readings, status="Rejected"
		)

		frappe.db.set_single_value("Stock Settings", "action_if_quality_inspection_is_rejected", "Stop")
		se.reload()
		self.assertRaises(
			QualityInspectionRejectedError, se.submit
		)  # when blocked in Stock settings, block rejected QI

		frappe.db.set_single_value("Stock Settings", "action_if_quality_inspection_is_rejected", "Warn")
		se.reload()
		se.submit()  # when allowed in Stock settings, allow rejected QI

		# teardown
		qa.reload()
		qa.cancel()
		se.reload()
		se.cancel()
		frappe.db.set_single_value("Stock Settings", "action_if_quality_inspection_is_rejected", "Stop")

	def test_qi_status(self):
		make_stock_entry(
			item_code="_Test Item with QA", target="_Test Warehouse - _TC", qty=1, basic_rate=100
		)
		dn = create_delivery_note(item_code="_Test Item with QA", do_not_submit=True)
		qa = create_quality_inspection(
			reference_type="Delivery Note", reference_name=dn.name, status="Accepted", do_not_save=True
		)
		qa.readings[0].manual_inspection = 1
		qa.save()

		# Case - 1: When there are one or more readings with rejected status and parent manual inspection is unchecked, then parent status should be set to rejected.
		qa.status = "Accepted"
		qa.manual_inspection = 0
		qa.readings[0].status = "Rejected"
		qa.save()
		self.assertEqual(qa.status, "Rejected")

		# Case - 2: When all readings have accepted status and parent manual inspection is unchecked, then parent status should be set to accepted.
		qa.status = "Rejected"
		qa.manual_inspection = 0
		qa.readings[0].status = "Accepted"
		qa.save()
		self.assertEqual(qa.status, "Accepted")

		# Case - 3: When parent manual inspection is checked, then parent status should not be changed.
		qa.status = "Accepted"
		qa.manual_inspection = 1
		qa.readings[0].status = "Rejected"
		qa.save()
		self.assertEqual(qa.status, "Accepted")

	@change_settings("System Settings", {"number_format": "#.###,##"})
	def test_diff_number_format(self):
		self.assertEqual(frappe.db.get_default("number_format"), "#.###,##")  # sanity check

		# Test QI based on acceptance values (Non formula)
		dn = create_delivery_note(item_code="_Test Item with QA", do_not_submit=True)
		readings = [
			{
				"specification": "Iron Content",  # numeric reading
				"min_value": 60,
				"max_value": 100,
				"reading_1": "70,000",
			},
			{
				"specification": "Iron Content",  # numeric reading
				"min_value": 60,
				"max_value": 100,
				"reading_1": "1.100,00",
			},
		]

		qa = create_quality_inspection(
			reference_type="Delivery Note", reference_name=dn.name, readings=readings, do_not_save=True
		)

		qa.save()

		# status must be auto set as per formula
		self.assertEqual(qa.readings[0].status, "Accepted")
		self.assertEqual(qa.readings[1].status, "Rejected")

		qa.delete()
		dn.delete()

	def test_delete_quality_inspection_linked_with_stock_entry(self):
		item_code = create_item("_Test Cicuular Dependecy Item with QA").name

		se = make_stock_entry(
			item_code=item_code, target="_Test Warehouse - _TC", qty=1, basic_rate=100, do_not_submit=True
		)

		se.inspection_required = 1
		se.save()

		qa = create_quality_inspection(
			item_code=item_code, reference_type="Stock Entry", reference_name=se.name, do_not_submit=True
		)

		se.reload()
		se.items[0].quality_inspection = qa.name
		se.save()

		qa.delete()

		se.reload()

		qc = se.items[0].quality_inspection
		self.assertFalse(qc)

		se.delete()

	def test_qa_for_pr_TC_SCK_159(self):
		from erpnext.accounts.doctype.payment_entry.test_payment_entry import create_company
		from erpnext.buying.doctype.supplier.test_supplier import create_supplier
		from erpnext.buying.doctype.purchase_order.test_purchase_order import get_or_create_fiscal_year
		create_company()

		create_supplier(supplier_name = "_Test Supplier")
		create_warehouse(
			warehouse_name="_Test Warehouse - _TC",
			properties={"parent_warehouse": "All Warehouses - _TC"},
			company="_Test Company",
		)
		get_or_create_fiscal_year("_Test Company")
		create_warehouse(
			warehouse_name="_Test Warehouse 1 - _TC",
			properties={"parent_warehouse": "All Warehouses - _TC"},
			company="_Test Company",
		)
		item_code = create_item("_Test Item with QA", valuation_rate=200).name
		pr = make_purchase_receipt(item_code = item_code, company = "_Test Company", stock_uom = "Box" , do_not_submit=True)

		frappe.db.set_value("Item", "_Test Item with QA", "inspection_required_before_purchase", 1)
		qa = create_quality_inspection(
			reference_type="Purchase Receipt", reference_name=pr.name, status="Accepted", inspection_type="Incoming", do_not_submit=True
		)
		pr.reload()
		qa.reload()
		self.assertEqual(qa.docstatus, 0)
		qa.submit()
		qa.reload()
		pr.reload()
		pr.submit()
		self.assertEqual(qa.status, "Accepted")

		qa.reload()
		qa.cancel()
		pr.reload()
		pr.cancel()

	def test_qa_for_pi_TC_SCK_160(self):
		from erpnext.accounts.doctype.payment_entry.test_payment_entry import create_company
		from erpnext.buying.doctype.supplier.test_supplier import create_supplier
		from erpnext.selling.doctype.sales_order.test_sales_order import get_or_create_fiscal_year
		from datetime import date
		create_company()
		create_warehouse(
			warehouse_name="_Test Warehouse 1 - _TC",
			properties={"parent_warehouse": "All Warehouses - _TC"},
			company="_Test Company",
		)
		get_or_create_fiscal_year("_Test Company")
		create_supplier(supplier_name="_Test Supplier")

		pr = make_purchase_invoice(item_code="_Test Item with QA",uom = "Box",do_not_save =True)
		pr.due_date = date.today()
		pr.save()
		pr.submit()
		frappe.db.set_value("Item", "_Test Item with QA", "inspection_required_before_purchase", 1)
		qa = create_quality_inspection(
			reference_type="Purchase Invoice", reference_name=pr.name, status="Accepted", inspection_type="Incoming", do_not_submit=True
		)
		pr.reload()
		qa.reload()
		self.assertEqual(qa.docstatus, 0)
		qa.submit()
		qa.reload()
		self.assertEqual(qa.status, "Accepted")

		qa.reload()
		qa.cancel()
		pr.reload()
		pr.cancel()

	@change_settings("Stock Settings",{"allow_negative_stock": 1})
	def test_qa_for_dn_TC_SCK_161(self):
		dn = create_delivery_note(item_code="_Test Item with QA", do_not_submit=True)

		self.assertRaises(QualityInspectionRequiredError, dn.submit)

		qa = create_quality_inspection(
			reference_type="Delivery Note", reference_name=dn.name, status="Rejected"
		)
		dn.reload()
		self.assertRaises(QualityInspectionRejectedError, dn.submit)

		frappe.db.set_value("Quality Inspection", qa.name, "status", "Accepted")
		dn.reload()
		dn.submit()

		qa.reload()
		qa.cancel()
		dn.reload()
		dn.cancel()

	def test_qa_for_si_TC_SCK_163(self):
		si = create_sales_invoice(item_code="_Test Item with QA")

		qa = create_quality_inspection(
			reference_type="Sales Invoice", reference_name=si.name, status="Accepted", inspection_type="Incoming", do_not_submit=True
		)
		si.reload()
		qa.reload()
		self.assertEqual(qa.docstatus, 0)
		qa.submit()
		qa.reload()
		self.assertEqual(qa.status, "Accepted")

		qa.reload()
		qa.cancel()
		si.reload()
		si.cancel()

	def test_qa_for_pr_out_TC_SCK_162(self):
		from erpnext.accounts.doctype.payment_entry.test_payment_entry import create_company
		from erpnext.buying.doctype.supplier.test_supplier import create_supplier
		from erpnext.buying.doctype.purchase_order.test_purchase_order import get_or_create_fiscal_year
		create_company()
		create_supplier(supplier_name = "_Test Supplier")
		create_warehouse(
			warehouse_name="_Test Warehouse - _TC",
			properties={"parent_warehouse": "All Warehouses - _TC"},
			company="_Test Company",
		)
		get_or_create_fiscal_year("_Test Company")
		create_warehouse(
			warehouse_name="_Test Warehouse 1 - _TC",
			properties={"parent_warehouse": "All Warehouses - _TC"},
			company="_Test Company",
		)
		item_code = create_item("_Test Item with QA", valuation_rate=200).name

		pr = make_purchase_receipt(item_code = item_code, company = "_Test Company",stock_uom= "Box", do_not_submit=True)

		frappe.db.set_value("Item", "_Test Item with QA", "inspection_required_before_purchase", 1)
		qa = create_quality_inspection(
			reference_type="Purchase Receipt", reference_name=pr.name, status="Accepted", inspection_type="Outgoing", do_not_submit=True
		)
		pr.reload()
		qa.reload()
		self.assertEqual(qa.docstatus, 0)
		qa.submit()
		pr.reload()
		pr.submit()
		qa.reload()
		self.assertEqual(qa.status, "Accepted")
		qa.reload()
		qa.cancel()
		pr.reload()
		pr.cancel()

	def test_qa_for_se_inc_TC_SCK_164(self):
		item_code = create_item("_Test SE Item with QA").name
		create_company()
		warehouse = create_warehouse("_Test warehouse PO", company="_Test Company QA")

		se = make_stock_entry(
			item_code=item_code, target=warehouse, qty=1, basic_rate=100, do_not_submit=True
		)

		se.inspection_required = 1
		se.save()

		qa = create_quality_inspection(
			item_code=item_code, reference_type="Stock Entry", reference_name=se.name, inspection_type="Incoming", do_not_submit=True
		)

		se.reload()
		qa.reload()
		self.assertEqual(qa.docstatus, 0)
		qa.submit()
		qa.reload()
		self.assertEqual(qa.status, "Accepted")

		qa.reload()
		qa.cancel()

	def test_qa_for_se_out_TC_SCK_165(self):
		item_code = create_item("_Test SE Item with QA").name
		create_company()
		warehouse = create_warehouse("_Test warehouse PO", company="_Test Company QA")

		se = make_stock_entry(
			item_code=item_code, target=warehouse, qty=1, basic_rate=100, do_not_submit=True
		)

		se.inspection_required = 1
		se.save()

		qa = create_quality_inspection(
			item_code=item_code, reference_type="Stock Entry", reference_name=se.name, inspection_type="Outgoing", do_not_submit=True
		)

		se.reload()
		qa.reload()
		self.assertEqual(qa.docstatus, 0)
		qa.submit()
		qa.reload()
		self.assertEqual(qa.status, "Accepted")

		qa.reload()
		qa.cancel()

	def test_qa_for_pr_proc_TC_SCK_166(self):
		from erpnext.accounts.doctype.payment_entry.test_payment_entry import create_company
		from erpnext.buying.doctype.supplier.test_supplier import create_supplier
		from erpnext.buying.doctype.purchase_order.test_purchase_order import get_or_create_fiscal_year
		create_company()
		create_supplier(supplier_name = "_Test Supplier")
		create_warehouse(
			warehouse_name="_Test Warehouse - _TC",
			properties={"parent_warehouse": "All Warehouses - _TC"},
			company="_Test Company",
		)
		create_warehouse(
			warehouse_name="_Test Warehouse 1 - _TC",
			properties={"parent_warehouse": "All Warehouses - _TC"},
			company="_Test Company",
		)
		get_or_create_fiscal_year("_Test Company")
		item_code = create_item("_Test Item with QA", valuation_rate=200).name
		pr = make_purchase_receipt(item_code = item_code, uom ="Box" ,stock_uom = "Box" ,do_not_submit=True)
		frappe.db.set_value("Item", "_Test Item with QA", "inspection_required_before_purchase", 1)

		qa = create_quality_inspection(
			reference_type="Purchase Receipt", reference_name=pr.name, status="Accepted", inspection_type="In Process", do_not_submit=True
		)
		pr.reload()
		qa.reload()
		self.assertEqual(qa.docstatus, 0)
		qa.submit()
		qa.reload()
		pr.reload()
		pr.submit()
		self.assertEqual(qa.status, "Accepted")

		qa.reload()
		qa.cancel()
		pr.reload()
		pr.cancel()

	def test_qa_for_dn_prcs_TC_SCK_167(self):
		dn = create_delivery_note(item_code="_Test Item with QA", do_not_submit=True)
		self.assertRaises(QualityInspectionRequiredError, dn.submit)

		qa = create_quality_inspection(
			reference_type="Delivery Note", reference_name=dn.name, status="Rejected", inspection_type="In Process"
		)
		dn.reload()
		self.assertRaises(QualityInspectionRejectedError, dn.submit)
		frappe.db.set_value("Quality Inspection", qa.name, "status", "Accepted")
		qa.reload()
		qa.cancel()

	def test_qa_for_dn_out_TC_SCK_168(self):
		dn = create_delivery_note(item_code="_Test Item with QA", do_not_submit=True)
		self.assertRaises(QualityInspectionRequiredError, dn.submit)

		qa = create_quality_inspection(
			reference_type="Delivery Note", reference_name=dn.name, status="Rejected", inspection_type="Outgoing"
		)
		dn.reload()
		self.assertRaises(QualityInspectionRejectedError, dn.submit)
		frappe.db.set_value("Quality Inspection", qa.name, "status", "Accepted")
		qa.reload()
		qa.cancel()

def create_quality_inspection(**args):
	args = frappe._dict(args)
	qa = frappe.new_doc("Quality Inspection")
	qa.report_date = nowdate()
	qa.inspection_type = args.inspection_type or "Outgoing"
	qa.reference_type = args.reference_type
	qa.reference_name = args.reference_name
	qa.item_code = args.item_code or "_Test Item with QA"
	qa.sample_size = 1
	qa.inspected_by = frappe.session.user
	qa.status = args.status or "Accepted"

	if not args.readings:
		create_quality_inspection_parameter("Size")
		readings = {"specification": "Size", "min_value": 0, "max_value": 10}
		if args.status == "Rejected":
			readings["reading_1"] = "12"  # status is auto set in child on save
	else:
		readings = args.readings

	if isinstance(readings, list):
		for entry in readings:
			create_quality_inspection_parameter(entry["specification"])
			qa.append("readings", entry)
	else:
		qa.append("readings", readings)

	if not args.do_not_save:
		qa.save()
		if not args.do_not_submit:
			qa.submit()

	return qa


def create_quality_inspection_parameter(parameter):
	if not frappe.db.exists("Quality Inspection Parameter", parameter):
		frappe.get_doc(
			{"doctype": "Quality Inspection Parameter", "parameter": parameter, "description": parameter}
		).insert()

def create_company():
	company_name = "_Test Company QA"
	if not frappe.db.exists("Company", company_name):
		company = frappe.new_doc("Company")
		company.company_name = company_name
		company.country="India",
		company.default_currency= "INR",
		company.create_chart_of_accounts_based_on= "Standard Template",
		company.chart_of_accounts= "Standard",
		company = company.save()
		company.load_from_db()
	return company_name
