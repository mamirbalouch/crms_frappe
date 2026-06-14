import frappe
from frappe.model.document import Document


class CaseProject(Document):
	def before_insert(self):
		if not self.creation_date:
			self.creation_date = frappe.utils.today()
