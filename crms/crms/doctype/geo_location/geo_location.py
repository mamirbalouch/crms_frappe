import frappe
from frappe.model.document import Document


class GeoLocation(Document):
	def before_insert(self):
		if not self.date_of_entry:
			self.date_of_entry = frappe.utils.today()
