# Copyright (c) 2026, Pratikshya Gochhayat and contributors
# For license information, please see license.txt

import frappe


def clear_custom_order_id_on_cancel(doc, method=None):
	"""Clear Order ID on item lines when the Sales Order is cancelled.

	``custom_order_id`` is unique in the database; cancelled rows would otherwise
	block reusing the same Sauda Booking line on a new Sales Order.
	"""
	for row in doc.get("items") or []:
		if getattr(row, "custom_order_id", None):
			row.custom_order_id = None
