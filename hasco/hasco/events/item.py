# Copyright (c) 2026, Pratikshya Gochhayat and contributors
# For license information, please see license.txt

import frappe

from hasco.hasco.install import TEST_GST_HSN_CODE


def ensure_gst_hsn_for_test_items(doc, method=None):
	"""ERPNext Item test_records omit gst_hsn_code; india_compliance requires it for sales items."""
	if not getattr(frappe.flags, "in_test", False):
		return
	if not frappe.db.exists("DocType", "GST HSN Code"):
		return
	if not doc.get("is_sales_item"):
		return
	if doc.get("gst_hsn_code"):
		return
	if not frappe.db.exists("GST HSN Code", TEST_GST_HSN_CODE):
		return
	doc.gst_hsn_code = TEST_GST_HSN_CODE
