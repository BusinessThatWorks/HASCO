# Copyright (c) 2026, Pratikshya Gochhayat and contributors
# For license information, please see license.txt

"""Backfill Sales Order Item.custom_order_id for rows created before that field existed."""

from collections import defaultdict

import frappe
from frappe.utils import cint, flt

from hasco.hasco.doctype.sauda_booking.sauda_booking import (
	make_sauda_order_id,
	resolve_sauda_booking_item_to_variant_item_code,
)


def execute():
	if not frappe.get_meta("Sales Order Item").has_field("custom_order_id"):
		return

	rows = frappe.db.sql(
		"""
		SELECT name, parent, item_code, qty, rate, idx, custom_reference
		FROM `tabSales Order Item`
		WHERE IFNULL(custom_reference, '') != ''
		AND IFNULL(custom_order_id, '') = ''
		""",
		as_dict=True,
	)

	if not rows:
		return

	# One Sauda Booking can be referenced from more than one Sales Order (bad data) or lines
	# already have order_ids from a previous mapper run. Process per booking so idx reservation
	# is global for that `custom_reference`, not per (booking, parent) pair.
	by_booking = defaultdict(list)
	for r in rows:
		by_booking[r.custom_reference].append(r)

	updated = 0
	skipped = 0
	unmatched = []

	for booking_name in sorted(by_booking.keys()):
		so_items = by_booking[booking_name]
		if not frappe.db.exists("Sauda Booking", booking_name):
			skipped += len(so_items)
			unmatched.append(f"missing Sauda Booking {booking_name!r} ({len(so_items)} row(s))")
			continue

		booking = frappe.get_doc("Sauda Booking", booking_name)
		cache = {}
		sauda_rows_sorted = sorted(
			list(booking.get("table_ulgv") or []),
			key=lambda x: cint(x.idx or 0),
		)
		so_items_sorted = sorted(so_items, key=lambda x: (x.parent, cint(x.idx or 0)))
		used_sauda_idx = _indices_already_used_for_booking(booking_name)

		for so_row in so_items_sorted:
			item_code = so_row.item_code
			qty = flt(so_row.qty)
			rate = flt(so_row.rate)

			matched = _match_and_set(
				booking_name,
				sauda_rows_sorted,
				so_row,
				item_code,
				qty,
				rate,
				cache,
				used_sauda_idx,
				strict_qty_rate=True,
			)
			if matched:
				updated += 1
				continue

			matched = _match_and_set(
				booking_name,
				sauda_rows_sorted,
				so_row,
				item_code,
				qty,
				rate,
				cache,
				used_sauda_idx,
				strict_qty_rate=False,
			)
			if matched:
				updated += 1
				continue

			skipped += 1
			unmatched.append(f"SO Item {so_row.name} (parent {so_row.parent!r}, booking {booking_name!r})")

	if unmatched:
		frappe.log_error(
			title="Backfill custom_order_id: unmatched rows",
			message="\n".join(unmatched[:50])
			+ (f"\n... and {len(unmatched) - 50} more" if len(unmatched) > 50 else ""),
		)

	frappe.logger(module="hasco").info(
		f"backfill_sales_order_item_custom_order_id: updated={updated}, skipped={skipped}"
	)


def _indices_already_used_for_booking(booking_name: str) -> set:
	"""Child-table indices already present in `custom_order_id` for this Sauda Booking link."""
	used = set()
	prefix = f"{booking_name}-"
	rows = frappe.get_all(
		"Sales Order Item",
		filters={"custom_reference": booking_name, "custom_order_id": ("!=", "")},
		pluck="custom_order_id",
	)
	for oid in rows:
		if not oid or not oid.startswith(prefix):
			continue
		suffix = oid[len(prefix) :]
		if suffix.isdigit():
			used.add(int(suffix))
	return used


def _order_id_is_free(oid: str, so_item_name: str) -> bool:
	"""Unique `custom_order_id`: allow only if unused or already owned by this row."""
	owner = frappe.db.get_value("Sales Order Item", {"custom_order_id": oid}, "name")
	return owner is None or owner == so_item_name


def _match_and_set(
	booking_name,
	sauda_rows_sorted,
	so_row,
	item_code,
	qty,
	rate,
	cache,
	used_sauda_idx,
	*,
	strict_qty_rate,
):
	for srow in sauda_rows_sorted:
		si = cint(srow.idx or 0)
		if si in used_sauda_idx:
			continue
		resolved = resolve_sauda_booking_item_to_variant_item_code(srow, cache)
		if resolved != item_code:
			continue
		if strict_qty_rate:
			if flt(srow.quantity) != qty or flt(srow.rate) != rate:
				continue

		oid = make_sauda_order_id(booking_name, srow)
		if not _order_id_is_free(oid, so_row.name):
			continue

		frappe.db.set_value(
			"Sales Order Item",
			so_row.name,
			"custom_order_id",
			oid,
			update_modified=False,
		)
		used_sauda_idx.add(si)
		return True

	return False
