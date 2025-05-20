# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.core.doctype.file.file import File
from frappe.utils.file_manager import get_file_path

class RemittanceofTDScertificate(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:  # pragma: no cover
		from erpnext.buying.doctype.logs.logs import logs
		from frappe.types import DF

		amended_from: DF.Link | None
		description: DF.Text | None
		email_template: DF.Link
		error_logs: DF.Table[logs]
		naming_series: DF.Literal["TDS-.#####"]
		sender: DF.Link | None
		sender_email: DF.Data | None
		subject: DF.Data | None
		upload_doc: DF.Attach
	# end: auto-generated types

	@frappe.whitelist(allow_guest=True)
	def unpack(self):
		# frappe.set_user("Administrator")
		self.error_logs = []
		file_name = self.upload_doc.split("/")[-1]
		unzip_file(file_name)
		list_of_receipient = get_email_list(self)

		try:
			for item in list_of_receipient:
				attachent = create_attachment(item)
				email_subject = self.subject 
				frappe.sendmail(recipients=item['email_id'],sender=self.sender_email,message = self.description, subject=email_subject, attachments=[attachent])
			return 1
		except Exception as e:
			frappe.msgprint(f"Error in sending Email check logs :{e}")

def unzip_file(name: str):
	"""Unzip the given file and make file records for each of the extracted files"""
	file: File = frappe.get_doc("File",{'file_name':name})
	return file.unzip()

def get_email_list(doc):

	certificate_name_list = frappe.db.get_list("File", filters={'attached_to_name':doc.name},fields=['file_name'])

	pan_list_with_file_name = get_pan_list(certificate_name_list)
	
	unrecorded_pan_list,emails_and_pan_list,pan_without_emails = get_emails_and_unrecored_pan_list(pan_list_with_file_name)
	
	error_logs = unrecorded_pan_list + pan_without_emails + emails_and_pan_list

	for log in error_logs:
		row = doc.append('error_logs', {})
		row.reason = log['reason']
		row.file_name = log['file_name']
		row.pan = log['pan']
		row.supplier = log['supplier_name']
		row.status = log['status']

	return emails_and_pan_list

def get_pan_list(certificate_name_list):
	pan_list_with_file_name = []
	for certi in certificate_name_list:
		object = {}
		certi = str(certi.file_name)
		if certi.endswith(".pdf"):
			object['file_name'] = certi
			object['pan']  = str(certi[:10])
			pan_list_with_file_name.append(object)
	return pan_list_with_file_name

def get_emails_and_unrecored_pan_list(pan_list_with_file_name):
	unrecorded_pan,emails_and_pan_list = [],[]
	pan_without_emails = []

	for item in pan_list_with_file_name:
		pan_and_email = frappe.db.get_value('Supplier',{'pan':item['pan']},['supplier_name','pan','email_id'],as_dict=1)

		if pan_and_email:
			if pan_and_email.email_id:
				item['supplier_name'] = pan_and_email.supplier_name
				item['email_id'] = pan_and_email.email_id
				item['status'] = "Success"
				item['reason'] = "Email Send Successfully to "+" : "+ pan_and_email.supplier_name + ":"+item['pan']
				emails_and_pan_list.append(item)
			else:
				item['supplier_name'] = pan_and_email.supplier_name
				item['reason'] = "Supplier without email_id" +" : "+ pan_and_email.supplier_name + ":"+item['pan']
				item['status'] = "Failure"
				pan_without_emails.append(item)
		else:
			item['supplier_name'] = ""
			item['reason'] = item['pan']+" : "+"PAN number not found in supplier"
			item['status'] = "Failure"
			unrecorded_pan.append(item)
	
	return  unrecorded_pan,emails_and_pan_list,pan_without_emails

def create_attachment(item):
	path = get_file_path(item['file_name'],)  

	with open(path, "rb") as fileobj:
		filedata = fileobj.read() 

	out = {"fname": item['file_name'],"fcontent": filedata}
	return out
