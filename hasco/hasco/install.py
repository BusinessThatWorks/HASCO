# Copyright (c) 2026, Pratikshya Gochhayat and contributors
# For license information, please see license.txt

"""Site install / test bootstrap hooks."""

import frappe

# 6-digit HSN used only when `frappe.flags.in_test` fills missing Item.gst_hsn_code (india_compliance).
TEST_GST_HSN_CODE = "999999"


def before_tests():
	"""Ensure GST HSN exists so ERPNext Item test_records can insert with india_compliance enabled."""
	if not frappe.db.exists("DocType", "GST HSN Code"):
		return
	ensure_test_gst_hsn_code()


def ensure_test_gst_hsn_code():
	if frappe.db.exists("GST HSN Code", TEST_GST_HSN_CODE):
		return
	doc = frappe.new_doc("GST HSN Code")
	doc.hsn_code = TEST_GST_HSN_CODE
	doc.description = "Test HSN (bench run-tests; india_compliance Item validation)"
	doc.flags.ignore_permissions = True
	doc.insert()
	frappe.db.commit()
