import frappe


def execute():
	"""Ensure Sales Order Item.gst_hsn_code is visible in list/grid view."""
	filters = {
		"doctype_or_field": "DocField",
		"doc_type": "Sales Order Item",
		"field_name": "gst_hsn_code",
		"property": "in_list_view",
	}

	ps_name = frappe.db.get_value("Property Setter", filters, "name")
	if ps_name:
		ps = frappe.get_doc("Property Setter", ps_name)
	else:
		ps = frappe.new_doc("Property Setter")
		ps.doctype_or_field = "DocField"
		ps.doc_type = "Sales Order Item"
		ps.field_name = "gst_hsn_code"
		ps.property = "in_list_view"
		ps.property_type = "Check"
		ps.module = "hasco"

	ps.value = "1"
	ps.save(ignore_permissions=True)
