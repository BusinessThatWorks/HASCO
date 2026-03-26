# Copyright (c) 2026, Pratikshya Gochhayat and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
from frappe.model.utils import get_fetch_values
from frappe.utils import flt


class SaudaBooking(Document):
	pass


@frappe.whitelist()
def make_sales_order(source_name: str, target_doc=None, args=None):
	"""Create a Sales Order from a submitted Sauda Booking.

	When invoked from Sales Order -> "Get Items From", `args` can include:
	- `filtered_children`: list of selected "Sauda Booking Item" row names
	"""
	if args is None:
		args = {}

	return _make_sales_order(
		source_name,
		target_doc=target_doc,
		args=args,
		ignore_permissions=False,
	)


def _make_sales_order(source_name: str, target_doc=None, ignore_permissions=False, args=None):
	if args is None:
		args = {}
	if isinstance(args, str):
		args = json.loads(args)

	target_doc_data = target_doc
	if isinstance(target_doc_data, str):
		target_doc_data = json.loads(target_doc_data)

	# Also block remapping in the same unsaved Sales Order (in-memory items).
	existing_refs_in_target = set()
	if target_doc_data and hasattr(target_doc_data, "get"):
		for row in target_doc_data.get("items", []) or []:
			ref = row.get("custom_reference") if hasattr(row, "get") else None
			if ref:
				existing_refs_in_target.add(ref)
	if source_name in existing_refs_in_target:
		frappe.throw(_("Sauda Booking {0} is already mapped to this Sales Order.").format(source_name))

	already_mapped = frappe.db.exists(
		"Sales Order Item",
		{
			"custom_reference": source_name,
			"docstatus": ("!=", 2),
		},
	)
	if already_mapped:
		frappe.throw(_("Sauda Booking {0} is already mapped to a Sales Order.").format(source_name))

	# Cache resolved Item variants to avoid repeated DB lookups.
	resolved_item_cache = {}

	def set_missing_values(source, target):
		target.flags.ignore_permissions = ignore_permissions

		# Header mappings
		if source.get("party_name"):
			target.customer = source.party_name
		if source.get("date"):
			target.transaction_date = source.date
		if source.get("communication_medium"):
			target.custom_booking_medium = source.communication_medium

		target.run_method("set_missing_values")
		target.run_method("calculate_taxes_and_totals")

	def select_item(d):
		# MultiSelectDialog sends `filtered_children` = selected child row names.
		# If it's empty, map all items for the selected Sauda Booking(s).
		filtered_items = (args or {}).get("filtered_children", [])
		return d.name in filtered_items if filtered_items else True

	def resolve_item_code(sauda_item):
		"""Resolve the actual variant Item code from Sauda Booking Item's grade + dimension."""
		grade = sauda_item.get("grade")
		dimension = sauda_item.get("dimension")
		if not grade or not dimension:
			return None

		key = (grade, dimension)
		if key in resolved_item_cache:
			return resolved_item_cache[key]

		# `grade` is a template item (has_variants=1). The corresponding variant is
		# identified by matching `dimension` against Item Variant Attribute.attribute_value.
		dimension_doc = frappe.get_cached_doc("Dimensions", dimension)

		# Candidates for attribute_value matching (depends on how Item variants were defined).
		candidates = [
			dimension_doc.name,
			getattr(dimension_doc, "mould_sizes", None),
			getattr(dimension_doc, "mould_length", None),
			f"{dimension_doc.get('mould_sizes')} - {dimension_doc.get('mould_length')}",
		]
		# Remove falsy + duplicates while keeping order.
		seen = set()
		candidates = [c for c in candidates if c and not (c in seen or seen.add(c))]

		# First try exact dimension.name match.
		item_code = frappe.db.get_value(
			"Item Variant Attribute",
			{"variant_of": grade, "attribute_value": dimension_doc.name},
			"parent",
		)
		if item_code:
			resolved_item_cache[key] = item_code
			return item_code

		# Fallback to any candidate.
		for val in candidates:
			item_code = frappe.db.get_value(
				"Item Variant Attribute",
				{"variant_of": grade, "attribute_value": val},
				"parent",
			)
			if item_code:
				resolved_item_cache[key] = item_code
				return item_code

		resolved_item_cache[key] = None
		return None

	def update_item(source, target, source_parent):
		# Resolve and set the actual variant Item code.
		target.item_code = resolve_item_code(source)
		if not target.item_code:
			# Condition should prevent this, but keep a hard guard.
			frappe.throw(
				_("No Item variant found for Grade {0} and Dimension {1}").format(
					source.get("grade"), source.get("dimension")
				)
			)

		# Map "Type Of Mould" into Sales Order Item child table.
		mould_type = source.get("mould_type")
		if not mould_type and source.get("dimension"):
			dimension_doc = frappe.get_cached_doc("Dimensions", source.get("dimension"))
			mould_type = dimension_doc.get("type_of_mould")

		if mould_type and target.meta.get_field("custom_type_of_mould"):
			target.custom_type_of_mould = mould_type

		# Copy Item-linked fields configured as fetch_from item_code.* (e.g. HSN/SAC on India GST).
		for fieldname, value in get_fetch_values("Sales Order Item", "item_code", target.item_code).items():
			if value is not None:
				target.set(fieldname, value)

		target.qty = flt(source.quantity)
		target.rate = flt(source.rate)
		target.amount = flt(source.amount)
		if source_parent and source_parent.get("name"):
			target.custom_reference = source_parent.name

	doclist = get_mapped_doc(
		"Sauda Booking",
		source_name,
		{
			"Sauda Booking": {
				"doctype": "Sales Order",
				"validation": {"docstatus": ["=", 1]},
				"field_map": {
					"party_name": "customer",
					"date": "transaction_date",
					"communication_medium": "custom_booking_medium",
				},
			},
			"Sauda Booking Item": {
				"doctype": "Sales Order Item",
				"field_map": {
					"quantity": "qty",
					"rate": "rate",
					"amount": "amount",
				},
				"postprocess": update_item,
				"condition": lambda d: select_item(d) and resolve_item_code(d),
			},
		},
		target_doc,
		set_missing_values,
		ignore_permissions=ignore_permissions,
	)

	return doclist
