# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils.file_manager import save_file


class DummyFile:
    def __init__(self, file_name):
        self.file_name = file_name

class TestRemittanceofTDScertificate(FrappeTestCase):
	def test_get_pan_list_TC_B_187(self):
		files = [
			DummyFile("ABCDE1234F_pan.pdf"),
			DummyFile("XYZ9876543_other.pdf"),
			DummyFile("invalid_file.txt")
		]

		from erpnext.buying.doctype.remittance_of_tds_certificate.remittance_of_tds_certificate import get_pan_list 
		result = get_pan_list(files)

		expected = [
			{"file_name": "ABCDE1234F_pan.pdf", "pan": "ABCDE1234F"},
			{"file_name": "XYZ9876543_other.pdf", "pan": "XYZ9876543"}
		]

		self.assertEqual(result, expected)
            
	def setUp(self):
		content = b"Dummy content"
		self.test_file = save_file(
			fname="test_attachment.txt",
			content=content,
			dt="User",
			dn=frappe.session.user,
			folder=None,
			decode=False
		)
		self.test_item = {"file_name": self.test_file.file_name}

	def test_create_attachment_TC_B_188(self):
		from erpnext.buying.doctype.remittance_of_tds_certificate.remittance_of_tds_certificate import create_attachment 
		result = create_attachment(self.test_item)

		self.assertIn("fname", result)
		self.assertIn("fcontent", result)
		self.assertEqual(result["fname"], "test_attachment.txt")
		self.assertEqual(result["fcontent"], b"Dummy content")
