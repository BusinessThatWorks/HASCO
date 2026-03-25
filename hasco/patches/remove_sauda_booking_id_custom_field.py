import frappe


def execute():
	"""Remove Sales Order header custom_sauda_booking_id field (if it exists)."""

	fieldname = "custom_sauda_booking_id"
	parent = "Sales Order"

	existing = frappe.db.get_value(
		"Custom Field",
		{"dt": parent, "fieldname": fieldname},
		"name",
	)
	if not existing:
		return

	frappe.delete_doc("Custom Field", existing, force=True)
