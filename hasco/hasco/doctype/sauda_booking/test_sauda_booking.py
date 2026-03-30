# Copyright (c) 2026, Pratikshya Gochhayat and Contributors
# See license.txt

import frappe
from erpnext.controllers.item_variant import create_variant
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt, today

from hasco.hasco.doctype.sauda_booking.sauda_booking import make_sales_order, make_sauda_order_id


class TestSaudaBooking(FrappeTestCase):
	def setUp(self) -> None:
		super().setUp()
		# Item variant resolution uses some globals; keep it deterministic per test run.
		frappe.flags.attribute_values = None

	def _make_gst_hsn_code(self, hsn_code: str = "998877"):
		if frappe.db.exists("GST HSN Code", hsn_code):
			return hsn_code

		gst_hsn = frappe.new_doc("GST HSN Code")
		gst_hsn.hsn_code = hsn_code
		gst_hsn.description = f"Test HSN {hsn_code}"
		gst_hsn.insert()
		return gst_hsn.hsn_code

	def _make_item_attribute_with_values(self, attribute_name: str, values: list[tuple[str, str]]):
		"""
		values: list of (attribute_value, abbr)
		"""
		if frappe.db.exists("Item Attribute", attribute_name):
			frappe.delete_doc("Item Attribute", attribute_name, force=1)

		attr = frappe.get_doc(
			{
				"doctype": "Item Attribute",
				"attribute_name": attribute_name,
				"item_attribute_values": [],
			}
		)
		for attribute_value, abbr in values:
			attr.append(
				"item_attribute_values",
				{"attribute_value": attribute_value, "abbr": abbr},
			)
		attr.insert()
		return attr

	def _make_item_template_with_variant_attr(self, template_item_code: str, attribute_name: str):
		if frappe.db.exists("Item", template_item_code):
			frappe.delete_doc("Item", template_item_code, force=1)

		# Keep this non-stock to avoid warehouse-related validations during Sales Order creation.
		# (The mapper under test only needs variant resolution.)
		item_group_name = f"Test Item Group - {frappe.generate_hash(6)}"
		if not frappe.db.exists("Item Group", item_group_name):
			parent = (
				frappe.db.get_value("Item Group", {"item_group_name": "All Item Groups"}, "name")
				or "All Item Groups"
			)
			frappe.get_doc(
				{
					"doctype": "Item Group",
					"item_group_name": item_group_name,
					"parent_item_group": parent,
					"is_group": 0,
				}
			).insert()

		if not frappe.db.exists("UOM", "Nos"):
			frappe.get_doc({"doctype": "UOM", "uom_name": "Nos", "must_be_whole_number": 0}).insert()

		template = frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": template_item_code,
				"item_name": template_item_code,
				"description": template_item_code,
				"item_group": item_group_name,
				"stock_uom": "Nos",
				"sales_uom": "Nos",
				"gst_hsn_code": self._make_gst_hsn_code(),
				"is_stock_item": 0,
				"has_variants": 1,
				"variant_based_on": "Item Attribute",
			}
		)
		template.append("attributes", {"attribute": attribute_name})
		template.insert()
		return template

	def _make_variant(self, template_item_code: str, attribute_name: str, attribute_value: str):
		# create_variant returns an unsaved Item (variant) doc.
		variant = create_variant(template_item_code, {attribute_name: attribute_value})
		# Ensure HSN is carried over for india_compliance item validation.
		template_gst_hsn = frappe.db.get_value("Item", template_item_code, "gst_hsn_code")
		if template_gst_hsn:
			variant.gst_hsn_code = template_gst_hsn
		variant.is_stock_item = 0
		variant.item_name = variant.item_code
		variant.save()
		return variant

	def _make_dimension(self, mould_sizes: str, mould_length: str, quantity: float):
		mould_type_value = f"Mould Type - {mould_sizes}-{mould_length}"
		mould_type_name = frappe.db.get_value("Mould Type", {"mould_type": mould_type_value}, "name")
		if not mould_type_name:
			mould_type_doc = frappe.get_doc(
				{
					"doctype": "Mould Type",
					"mould_type": mould_type_value,
				}
			)
			mould_type_doc.insert()
			mould_type_name = mould_type_doc.name

		# Dimensions autoname uses mould_sizes & mould_length, so this docname is stable.
		dimension = frappe.get_doc(
			{
				"doctype": "Dimensions",
				"mould_sizes": mould_sizes,
				"type_of_mould": mould_type_name,
				"mould_length": mould_length,
				"quantity": quantity,
			}
		)
		dimension.insert()
		return dimension

	def _make_customer(self, customer_name: str, custom_customer_code: str):
		if frappe.db.exists("Customer", customer_name):
			frappe.delete_doc("Customer", customer_name, force=1)

		customer = frappe.new_doc("Customer")
		customer.customer_name = customer_name
		customer.type = "Individual"
		customer.insert()

		customer.db_set("custom_customer_code", custom_customer_code)
		return frappe.get_doc("Customer", customer_name)

	def _make_sauda_booking(self, party_name: str, item_rows: list[dict]):
		sauda_booking = frappe.new_doc("Sauda Booking")
		sauda_booking.party_name = party_name
		sauda_booking.party_code = frappe.db.get_value("Customer", party_name, "custom_customer_code")
		sauda_booking.date = today()
		sauda_booking.communication_medium = "Phone"
		sauda_booking.sauda_type = "Sale"

		for row in item_rows:
			sauda_booking.append("table_ulgv", row)

		# For autoname: ensure party_code is computed from the customer's custom_customer_code.
		sauda_booking.flags.ignore_permissions = True
		sauda_booking.insert()
		sauda_booking.submit()
		return sauda_booking

	def test_make_sales_order_maps_item_variants(self):
		attribute_name = f"Test Dimension Attribute - {frappe.generate_hash(6)}"

		# Dimensions (also become Item Variant Attribute attribute_value via mapper)
		dimension_1 = self._make_dimension("10", "20", quantity=2.5)
		dimension_2 = self._make_dimension("11", "21", quantity=3.0)

		# Create item-variant attribute definitions where attribute_value matches Dimensions' docname.
		item_attribute = self._make_item_attribute_with_values(
			attribute_name=attribute_name,
			values=[(dimension_1.name, "D1"), (dimension_2.name, "D2")],
		)

		grade_template_code = f"TEST-GRADE-{frappe.generate_hash(6)}"
		template = self._make_item_template_with_variant_attr(grade_template_code, item_attribute.name)

		variant_1 = self._make_variant(template.item_code, item_attribute.name, dimension_1.name)
		variant_2 = self._make_variant(template.item_code, item_attribute.name, dimension_2.name)

		customer_code = f"CUST-{frappe.generate_hash(5)}"
		customer_name = f"_Test Sauda Customer {frappe.generate_hash(6)}"
		customer = self._make_customer(customer_name, customer_code)

		booking = self._make_sauda_booking(
			party_name=customer.name,
			item_rows=[
				{
					"grade": template.item_code,
					"dimension": dimension_1.name,
					"quantity": dimension_1.quantity,
					"rate": 100,
					"amount": flt(dimension_1.quantity) * 100,
				},
				{
					"grade": template.item_code,
					"dimension": dimension_2.name,
					"quantity": dimension_2.quantity,
					"rate": 250,
					"amount": flt(dimension_2.quantity) * 250,
				},
			],
		)

		so = make_sales_order(booking.name, args=None)

		self.assertEqual(so.doctype, "Sales Order")
		self.assertEqual(so.customer, customer.name)
		self.assertEqual(str(so.transaction_date), str(booking.date))
		self.assertEqual(so.custom_booking_medium, booking.communication_medium)
		# Header custom_sauda_booking_id is removed; mapper stores reference per item.
		self.assertTrue(all(d.custom_reference == booking.name for d in so.items))
		for so_item, sauda_row in zip(so.items, booking.table_ulgv, strict=True):
			self.assertEqual(so_item.custom_order_id, make_sauda_order_id(booking.name, sauda_row))

		so_item_codes = [d.item_code for d in so.items]
		self.assertIn(variant_1.item_code, so_item_codes)
		self.assertIn(variant_2.item_code, so_item_codes)

		# Verify mapped qty/rate/amount for one row explicitly.
		for so_item in so.items:
			if so_item.item_code == variant_1.item_code:
				self.assertEqual(flt(so_item.qty), flt(dimension_1.quantity))
				self.assertEqual(flt(so_item.rate), 100)
				self.assertEqual(flt(so_item.amount), flt(dimension_1.quantity) * 100)
				self.assertEqual(so_item.custom_type_of_mould, dimension_1.type_of_mould)
			elif so_item.item_code == variant_2.item_code:
				self.assertEqual(so_item.custom_type_of_mould, dimension_2.type_of_mould)

	def test_make_sales_order_filtered_children(self):
		attribute_name = f"Test Dimension Attribute - {frappe.generate_hash(6)}"

		dimension_1 = self._make_dimension("20", "30", quantity=1.5)
		dimension_2 = self._make_dimension("21", "31", quantity=2.0)

		item_attribute = self._make_item_attribute_with_values(
			attribute_name=attribute_name,
			values=[(dimension_1.name, "D1"), (dimension_2.name, "D2")],
		)

		grade_template_code = f"TEST-GRADE-{frappe.generate_hash(6)}"
		template = self._make_item_template_with_variant_attr(grade_template_code, item_attribute.name)

		variant_1 = self._make_variant(template.item_code, item_attribute.name, dimension_1.name)
		# Variant 2 exists but will be filtered out from the mapping.
		self._make_variant(template.item_code, item_attribute.name, dimension_2.name)

		customer_code = f"CUST-{frappe.generate_hash(5)}"
		customer_name = f"_Test Sauda Customer {frappe.generate_hash(6)}"
		customer = self._make_customer(customer_name, customer_code)

		booking = self._make_sauda_booking(
			party_name=customer.name,
			item_rows=[
				{
					"grade": template.item_code,
					"dimension": dimension_1.name,
					"quantity": dimension_1.quantity,
					"rate": 10,
					"amount": flt(dimension_1.quantity) * 10,
				},
				{
					"grade": template.item_code,
					"dimension": dimension_2.name,
					"quantity": dimension_2.quantity,
					"rate": 20,
					"amount": flt(dimension_2.quantity) * 20,
				},
			],
		)

		first_child_name = booking.table_ulgv[0].name

		so = make_sales_order(
			booking.name,
			args={"filtered_children": [first_child_name]},
		)

		self.assertEqual(len(so.items), 1)
		self.assertEqual(so.items[0].item_code, variant_1.item_code)
		self.assertEqual(
			so.items[0].custom_order_id,
			make_sauda_order_id(booking.name, booking.table_ulgv[0]),
		)

	def test_make_sales_order_two_bookings_one_sales_order(self):
		"""Append a second Sauda Booking onto the same draft Sales Order; Order ID uses each booking name + source row idx."""
		attribute_name = f"Test Dimension Attribute - {frappe.generate_hash(6)}"

		dimension_a = self._make_dimension("30", "40", quantity=1.0)
		dimension_b = self._make_dimension("31", "41", quantity=2.0)

		item_attribute = self._make_item_attribute_with_values(
			attribute_name=attribute_name,
			values=[(dimension_a.name, "DA"), (dimension_b.name, "DB")],
		)

		grade_template_code = f"TEST-GRADE-{frappe.generate_hash(6)}"
		template = self._make_item_template_with_variant_attr(grade_template_code, item_attribute.name)

		self._make_variant(template.item_code, item_attribute.name, dimension_a.name)
		self._make_variant(template.item_code, item_attribute.name, dimension_b.name)

		customer_code = f"CUST-{frappe.generate_hash(5)}"
		customer_name = f"_Test Sauda Customer {frappe.generate_hash(6)}"
		customer = self._make_customer(customer_name, customer_code)

		booking_one = self._make_sauda_booking(
			party_name=customer.name,
			item_rows=[
				{
					"grade": template.item_code,
					"dimension": dimension_a.name,
					"quantity": dimension_a.quantity,
					"rate": 50,
					"amount": flt(dimension_a.quantity) * 50,
				},
			],
		)
		booking_two = self._make_sauda_booking(
			party_name=customer.name,
			item_rows=[
				{
					"grade": template.item_code,
					"dimension": dimension_b.name,
					"quantity": dimension_b.quantity,
					"rate": 60,
					"amount": flt(dimension_b.quantity) * 60,
				},
			],
		)

		so = make_sales_order(booking_one.name, args=None)
		self.assertEqual(len(so.items), 1)
		so = make_sales_order(booking_two.name, target_doc=so, args=None)

		self.assertEqual(len(so.items), 2)
		by_ref = {row.custom_reference: row for row in so.items}
		self.assertEqual(set(by_ref.keys()), {booking_one.name, booking_two.name})

		self.assertEqual(
			by_ref[booking_one.name].custom_order_id,
			make_sauda_order_id(booking_one.name, booking_one.table_ulgv[0]),
		)
		self.assertEqual(
			by_ref[booking_two.name].custom_order_id,
			make_sauda_order_id(booking_two.name, booking_two.table_ulgv[0]),
		)
