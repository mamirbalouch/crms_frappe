import frappe
from frappe.model.document import Document

from crms.crms.api.cdr_import import _normalize_number


class WorkingNumber(Document):
	def autoname(self):
		# The name is just the (normalized) mobile number, e.g. 3137760580.
		# Only when that same number already exists (a different Case Project uses
		# it) do we qualify it with the Case Project code, e.g. 3137760580-CP0002.
		self._normalize()
		base = (self.working_mobile_number or "").strip()
		if base and frappe.db.exists("Working Number", base):
			self.name = f"{base}-{self.case_project}"
		else:
			self.name = base

	def validate(self):
		self._normalize()

	def _normalize(self):
		if self.working_mobile_number:
			normalized = _normalize_number(self.working_mobile_number)
			if normalized:
				self.working_mobile_number = normalized

	def before_insert(self):
		if not self.date_of_entry:
			self.date_of_entry = frappe.utils.today()
