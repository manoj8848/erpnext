import unittest

import frappe


class TestSmsCenter(unittest.TestCase):
    def setUp(self):
        from erpnext.buying.doctype.supplier.test_supplier import create_supplier
        
        if not frappe.db.exists("Customer", "_Test Customer"):
            frappe.get_doc({
                "doctype": "Customer",
                "customer_name": "_Test Customer"
            }).insert()

        if not frappe.db.exists("Contact", {"first_name": "Test", "last_name": "Customer"}):
            frappe.get_doc({
                "doctype": "Contact",
                "first_name": "Test",
                "last_name": "Customer",
                "mobile_no": "9999999999",
                "links": [{
                    "link_doctype": "Customer",
                    "link_name": "_Test Customer"
                }]
            }).insert()
            
        create_supplier(supplier_name="_Test Supplier")
        
        if not frappe.db.exists("Sales Partner", "_Test Coupon Partner"):
            frappe.get_doc(
                {
                    "doctype": "Sales Partner",
                    "partner_name": "_Test Coupon Partner",
                    "commission_rate": 2,
                    "referral_code": "COPART",
                }
            ).insert()
            
    def test_create_receiver_list_coverage_TC_S_188(self):
        send_to_options = [
            "All Customer Contact",
            "All Supplier Contact",
            "All Sales Partner Contact",
            "All Lead (Open)",
            "All Employee (Active)"
        ]

        for option in send_to_options:
            doc = frappe.get_doc({
                "doctype": "SMS Center",
                "send_to": option,
                "customer": "_Test Customer",
                "supplier": "_Test Supplier",
                "sales_partner": "_Test Coupon Partner"
            })
            doc.create_receiver_list()
            
            self.assertEqual(doc.send_to, option)
            
    def test_get_receiver_nos_coverage_TC_189(self):
        doc = frappe.get_doc({
                "doctype": "SMS Center",
                "receiver_list": "John Doe - 9876543210\nJane Smith - 9123456780"
            })
        result = doc.get_receiver_nos()
        self.assertEqual(result, ["9876543210", "9123456780"])

        doc.receiver_list = "9876543210\n9123456780"
        result = doc.get_receiver_nos()
        self.assertEqual(result, ["9876543210", "9123456780"])

        doc.receiver_list = "\n 9876543210 \n\nJane - 9000000000\n"
        result = doc.get_receiver_nos()
        self.assertEqual(result, ["9876543210", "9000000000"])

        doc.receiver_list = ""
        result = doc.get_receiver_nos()
        self.assertEqual(result, [])
        
    def test_send_sms_coverage_TC_S_194(self):
        doc = frappe.get_doc({
            "doctype": "SMS Center",
            "receiver_list": "John Doe - 9876543210\nJane Smith - 9123456780"
        })
        doc.send_sms()
        self.assertEqual(doc.message, None)
        
        doc.message = "Test Send SMS"
        doc.send_sms()
        self.assertEqual(doc.message, "Test Send SMS")
            