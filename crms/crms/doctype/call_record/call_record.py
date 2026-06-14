import frappe
from frappe.model.document import Document


class CallRecord(Document):
	def before_insert(self):
		if not self.upload_record_date:
			self.upload_record_date = frappe.utils.today()
