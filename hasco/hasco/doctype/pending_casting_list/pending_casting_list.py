# Copyright (c) 2026, Pratikshya Gochhayat and contributors
# For license information, please see license.txt
import frappe
from frappe import _
from frappe.model.document import Document


class PendingCastingList(Document):
	pass


@frappe.whitelist()
def fetch_items_from_sales_order(sales_order: str) -> dict:
	"""Populate `Pending Casting Items` from a given `Sales Order`."""
	if not sales_order:
		frappe.throw(_("Sales Order is required"))

	so = frappe.get_doc("Sales Order", sales_order)
	if so.docstatus == 2:
		frappe.throw(_("Cancelled Sales Order cannot be used"))

	order_type = None
	# Sauda Booking ID is stored at item-level (`custom_reference`) after removing
	# the Sales Order header custom field.
	for so_item in getattr(so, "items", []) or []:
		sauda_booking_id = so_item.get("custom_reference")
		if sauda_booking_id:
			sauda_booking = frappe.get_cached_doc("Sauda Booking", sauda_booking_id)
			order_type = sauda_booking.get("sauda_type")
			break

	order_status = None
	if getattr(so, "custom_order_status", None):
		# Sales Order: "By Party" / "By Us"
		# Pending Casting Items: "Hold by Party" / "Hold by Us"
		order_status = "Hold by Party" if so.custom_order_status == "By Party" else "Hold by Us"

	items = list(getattr(so, "items", []) or [])
	item_codes = [d.item_code for d in items if d.get("item_code")]

	grade_by_item_code = {}
	dimension_by_item_code = {}

	if item_codes:
		unique_item_codes = list(set(item_codes))
		variant_attrs = frappe.get_all(
			"Item Variant Attribute",
			filters={"parent": ["in", unique_item_codes]},
			fields=["parent", "variant_of", "attribute_value"],
		)

		attribute_values_set = {d.get("attribute_value") for d in variant_attrs if d.get("attribute_value")}
		attribute_values_set = {v for v in attribute_values_set if v}

		# Resolve Dimensions from any candidate stored on Item Variant Attribute:
		# - Dimensions.name
		# - Dimensions.mould_sizes
		# - Dimensions.mould_length
		# - "{mould_sizes} - {mould_length}"
		key_to_dimension = {}
		if attribute_values_set:
			dimension_rows = []
			dimension_rows.extend(
				frappe.get_all(
					"Dimensions",
					filters={"name": ["in", list(attribute_values_set)]},
					fields=["name", "mould_sizes", "mould_length"],
				)
			)
			dimension_rows.extend(
				frappe.get_all(
					"Dimensions",
					filters={"mould_sizes": ["in", list(attribute_values_set)]},
					fields=["name", "mould_sizes", "mould_length"],
				)
			)
			dimension_rows.extend(
				frappe.get_all(
					"Dimensions",
					filters={"mould_length": ["in", list(attribute_values_set)]},
					fields=["name", "mould_sizes", "mould_length"],
				)
			)

			unique_dims = {}
			for d in dimension_rows:
				if d.get("name"):
					unique_dims[d["name"]] = d

			for d in unique_dims.values():
				mould_sizes = d.get("mould_sizes")
				mould_length = d.get("mould_length")

				candidates = [d.get("name"), mould_sizes, mould_length]
				if mould_sizes and mould_length:
					candidates.append(f"{mould_sizes} - {mould_length}")

				for key in candidates:
					if key and key not in key_to_dimension:
						key_to_dimension[key] = d.get("name")

		for row in variant_attrs:
			item_code = row.get("parent")
			if not item_code:
				continue
			if row.get("variant_of") and item_code not in grade_by_item_code:
				grade_by_item_code[item_code] = row.get("variant_of")
			attr_val = row.get("attribute_value")
			if attr_val and attr_val in key_to_dimension and item_code not in dimension_by_item_code:
				dimension_by_item_code[item_code] = key_to_dimension.get(attr_val)

	def _add(child: dict, key: str, value):
		if value is None or value == "":
			return
		child[key] = value

	out_items = []
	for so_item in items:
		item_code = so_item.get("item_code")
		grade = grade_by_item_code.get(item_code)
		dimension = dimension_by_item_code.get(item_code)

		if not grade or not dimension:
			frappe.throw(_("Could not resolve Grade/Dimension for Sales Order item `{0}`").format(item_code))

		dimension_doc = frappe.get_cached_doc("Dimensions", dimension)

		child = {}
		_add(child, "grade", grade)
		_add(child, "item_code", item_code)
		_add(child, "dimension", dimension)
		_add(child, "mould_size", dimension_doc.get("mould_sizes"))
		_add(child, "hot_top_type", dimension_doc.get("hot_top_type"))

		process = so_item.get("custom_process_name")
		if process and frappe.db.exists("Process", process):
			child["link_vbsl"] = process

		_add(child, "order_type", order_type)
		_add(child, "order_status", order_status)

		other_info_val = so_item.get("custom_other_info")
		_add(child, "other_information", other_info_val)
		if other_info_val and frappe.db.exists("Other Info", other_info_val):
			child["other_info"] = other_info_val

		child["pick"] = "Pending"
		child["pick_date"] = None

		out_items.append(child)

	return {
		"party_name": so.get("customer"),
		"order_date": so.get("transaction_date"),
		"items": out_items,
	}


@frappe.whitelist()
def make_pending_casting_list_from_sales_order(sales_order: str) -> dict:
	"""Create (or update) a Pending Casting List from a Sales Order.

	- If a non-cancelled Pending Casting List already exists for the same Sales Order,
	  it will be updated (only when docstatus=0).
	- If it exists and is submitted (docstatus=1), we block updating to avoid tampering.
	"""
	if not sales_order:
		frappe.throw(_("Sales Order is required"))

	items_data = fetch_items_from_sales_order(sales_order) or {}

	existing = frappe.get_all(
		"Pending Casting List",
		filters={"sales_order": sales_order, "docstatus": ["!=", 2]},
		fields=["name", "docstatus"],
		order_by="modified desc",
		limit=1,
	)

	if existing:
		pl = frappe.get_doc("Pending Casting List", existing[0].name)
		if pl.docstatus == 1:
			frappe.throw(
				_(
					"Pending Casting List {0} is already submitted. Create a new one manually if required."
				).format(pl.name)
			)

		pl.party_name = items_data.get("party_name")
		pl.order_date = items_data.get("order_date")
		pl.sales_order = sales_order
		pl.clear_table("table_jthm")

		for row in items_data.get("items", []) or []:
			pl.append("table_jthm", row)

		pl.save(ignore_permissions=True)
		return {"name": pl.name, "updated": True}

	# Create new draft Pending Casting List.
	pl = frappe.new_doc("Pending Casting List")
	pl.sales_order = sales_order
	pl.party_name = items_data.get("party_name")
	pl.order_date = items_data.get("order_date")

	for row in items_data.get("items", []) or []:
		pl.append("table_jthm", row)

	pl.insert(ignore_permissions=True)
	return {"name": pl.name, "created": True}
