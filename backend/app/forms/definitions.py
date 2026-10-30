"""Every form the portal knows, as sections of fields (see fields.py for the building blocks).

The forms follow the sales templates in forms.md.
"""

from .fields import (INSCRIPTION, NOTES, address, amounts, attachments, client, discount_fields, f, files, money,
    original_refs, payment, request_info, section, yes_no)
from .options import (BASE_COLORS, CASH, CASH_PAYMENT, COLORS, COVER_BACKS, DESIGN_VERSIONS, FRONT_DESIGNS,
    HAS_INSCRIPTION, MAX_INSTALLATION_DAYS, MAINTENANCE_DEVICES, MAINTENANCE_SERVICES, MAX_PACKAGE_QUANTITY,
    OTHER_WORK_DAFTRA_ID, PACKAGE_COLOR_FAMILIES, PAID, PAYMENT_METHODS, REFUND_METHODS, RENEWAL_PRICE,
    TECH_SERVICE_DAFTRA_IDS, TECH_SERVICE_LABELS, TREASURY_BY_METHOD, W_DIRECTIONS, WANTS_WORK_ORDER, WORK_STARTED, WORK_STATUS)


FORM_TYPES = {
    "new_sale": {
        "label": "طلب بيع لعميل جديد",
        # Approving it creates the client (when new), the invoice and the receipt in Daftra
        "invoiced": True,
        "daftra_note": "ويُنشأ في دفترة العميل (إن كان جديدًا) والفاتورة وسند القبض بالمبلغ المدفوع، وأمر الشغل إن طُلب.",
        "sections": [
            request_info(invoiced=True),
            client(False, creates_client=True),
            address(),
            section(
                "تفاصيل الطلب",
                f("order_lines", "المنتجات والباقات", "order_lines", True, subtotal_field="subtotal_amount", line_fields=[
                    # How many of the package: every product in it (and its inscription) counts this many times
                    f("package_quantity", "الكمية (عدد الباقات)", "number", integer=True, min=1, max=MAX_PACKAGE_QUANTITY,
                      package_only=True, stepper=True),
                    f("cooler_color", "لون البرادة", "select", True, options=COLORS),
                    # Its choices depend on the package (PACKAGE_COLOR_FAMILIES); optional, as its label says
                    f("cover_color", "لون الغطاء، إن يوجد", "package_color", optional=True,
                      families=[{**family, "colors": [shown for shown, _ in family["colors"]]} for family in PACKAGE_COLOR_FAMILIES]),
                    # The build details the work order's form in Daftra asks for
                    f("front_design", "تصميم القطعة الأمامية، إن ينطبق", "select", options=FRONT_DESIGNS),
                    f("w_direction", "اتجاه الدبليو، إن ينطبق", "select", options=W_DIRECTIONS),
                    f("cover_back", "ظهر الكفر، إن ينطبق", "select", options=COVER_BACKS),
                    f("design_version", "التصميم قديم أم جديد، إن ينطبق", "select", options=DESIGN_VERSIONS),
                    f("base_color", "لون القاعدة، إن ينطبق", "select", options=BASE_COLORS),
                    INSCRIPTION[0],
                    # beside: shown on the same line as that field, taking a third of it
                    money("inscription_price", "سعر الكتابة، شامل الضريبة (درهم)", required_if=HAS_INSCRIPTION,
                          charge=True, beside="inscription"),
                    f("manufacturing_notes", "ملاحظات خاصة للتصنيع", "textarea"),
                ]),
                note="إرسال الطلب يعني أن العميل وافق على التصميم واللون والكتابة.",
            ),
            amounts(must_pay=True, auto_total=True, invoiced=True),
            payment(invoiced=True),
            attachments(
                files("payment_proof", "إثبات الدفع", True),
                files("design_image", "صورة التصميم واللون المعتمدين", True),
                files("inscription_file", "صورة / ملف الكتابة، إن وجدت"),
            ),
            NOTES,
            section(
                "التركيب وأمر الشغل",
                yes_no("create_work_order", "إنشاء أمر الشغل في دفترة"),
                # Any whole number of days (e.g. 15, 20, 17): the work order is due that many days after approval
                f("installation_days", "مدة التركيب (بالأيام)", "number", integer=True, min=1, max=MAX_INSTALLATION_DAYS,
                  placeholder="مثال: 15 أو 20", unit="يومًا", required_if=WANTS_WORK_ORDER),
                note="عند الاعتماد يُنشأ أمر الشغل في دفترة والمدير المعتمِد مسؤولًا عنه، يبدأ يوم الاعتماد وينتهي بعد مدة التركيب، ويُربط بالفاتورة.",
            ),
        ],
    },
    "contract_renewal": {
        "label": "طلب تجديد عقد الصيانة السنوي",
        # Approving it updates the client's category and creates the renewal invoice and receipt in Daftra
        "invoiced": True,
        "daftra_note": "ويُحدَّث تصنيف العميل في دفترة، وتُنشأ فاتورة التجديد وسند القبض بالمبلغ المدفوع.",
        "sections": [
            request_info("تاريخ الطلب", invoiced=True),
            {**client(False), "note": "التجديد لعميل موجود في دفترة فقط؛ ابحث عنه برقم الهاتف أو الكود."},
            address(),
            section(
                "تفاصيل الطلب",
                f("cooler_type", "نوع البرادة", required=True),
                f("cooler_notes", "ملاحظات على حالة البرادة، إن وجدت", "textarea"),
                note="الخدمة: تجديد عقد لمدة سنة، تبديل الفلاتر كل 3 شهور مع صيانة البرادة.",
            ),
            amounts(total_label="قيمة الطلب النهائية بعد الخصم، شامل الضريبة", must_pay=True, invoiced=True,
                    price_label="سعر تجديد العقد قبل الخصم، شامل الضريبة", price_default=RENEWAL_PRICE),
            payment(invoiced=True),
            attachments(files("payment_proof", "إثبات الدفع", True)),
            NOTES,
        ],
    },
    "maintenance": {
        "label": "طلب صيانة وتبديل",
        # Approving it creates the client (when new), the invoice with the chosen items, and the receipt
        "invoiced": True,
        "daftra_note": "ويُنشأ في دفترة العميل (إن كان جديدًا) وفاتورة البنود المختارة، وسند القبض إن وُجدت دفعة.",
        "sections": [
            request_info("تاريخ الطلب", invoiced=True),
            client(False, creates_client=True),
            address(),
            section(
                "تفاصيل الطلب",
                f("devices", "نوع الجهاز / البرادة (يمكن اختيار أكثر من جهاز)", "multiselect", True,
                  options=MAINTENANCE_DEVICES, dropdown=True),
                f("service", "الخدمة", "select", True, options=MAINTENANCE_SERVICES, dropdown=True),
                # Only the catalog's maintenance items (products with a maintenance group), at their catalog price
                f("order_lines", "إضافة بند", "order_lines", True, subtotal_field="subtotal_amount", items="maintenance"),
                f("visit_date", "تاريخ الزيارة", "date", True),
            ),
            section(
                "قيمة الطلب",
                f("subtotal_amount", "قيمة البنود قبل الخصم، شامل الضريبة", "number", money=True, computed=[]),
                f("total_amount", "قيمة الطلب النهائية بعد الخصم، شامل الضريبة", "number", money=True,
                  computed=["subtotal_amount", "discount_amount"], negative_message="قيمة الخصم أكبر من قيمة البنود"),
                *discount_fields(),
                # A maintenance visit is paid in full (or is free: 0)
                money("paid_amount", "المبلغ المدفوع فعليًا الآن", True, must_equal="total_amount",
                      must_equal_message="يجب دفع قيمة الطلب كاملة"),
            ),
            section(
                "تفاصيل الدفعة",
                f("payment_method", "طريقة الدفع", "select", options=PAYMENT_METHODS, required_if=PAID),
                f("treasury", "الخزينة / الحساب المستلم في دفترة", "daftra_treasury",
                  default_from={"field": "payment_method", "values": TREASURY_BY_METHOD}, required_if=PAID),
                f("payment_date", "تاريخ الدفع", "date", default="today", not_future=True, required_if=PAID),
                f("collector_name", "اسم المحصل، في حالة الدفع النقدي", "staff", required_if=CASH_PAYMENT),
            ),
            attachments(
                files("payment_proof", "إثبات الدفع، إن وُجدت دفعة", required_if=PAID),
                files("work_media", "صور / فيديو العطل أو الأعمال المنفذة، إن توفرت"),
            ),
            NOTES,
        ],
    },
    "balance_payment": {
        "label": "طلب تسديد مبلغ متبقي",
        # Approving it creates a receipt in Daftra on the chosen invoice; nothing else is created
        "invoiced": True,
        "daftra_note": "ويُنشأ في دفترة سند قبض بالمبلغ المدفوع على الفاتورة المختارة.",
        "sections": [
            request_info("تاريخ الطلب", source=False),
            section(
                "بيانات العميل",
                f("phone", "رقم الهاتف", "phone", True),
                f("client_code", "كود العميل", required=True, pattern=r"^\d{1,6}$", pattern_message="أرقام فقط، حتى 6 خانات"),
                f("customer_name", "اسم العميل", required=True, max_length=150),
                f("invoice", "رقم الفاتورة", "daftra_client_invoice", True),
                note="بعد العثور على العميل تظهر فواتيره التي عليها مبلغ متبقٍ، الأحدث أولًا.",
            ),
            section("قيمة الطلب", money("paid_amount", "المبلغ المدفوع الآن", True, positive=True)),
            section(
                "تفاصيل الدفعة",
                f("payment_method", "طريقة الدفع", "select", True, options=PAYMENT_METHODS),
                f("treasury", "الخزينة / الحساب المستلم في دفترة", "daftra_treasury", True,
                  default_from={"field": "payment_method", "values": TREASURY_BY_METHOD}),
                f("collector_name", "اسم المحصل", "staff", True),
                f("payment_date", "تاريخ التحصيل", "date", True, default="today", not_future=True),
                f("payment_reference", "رقم التحويل / السند الورقي", required=True),
            ),
            attachments(files("payment_proof", "صورة التحويل / الإيصال", True)),
            NOTES,
        ],
    },
    "quotation": {
        "label": "طلب عرض سعر",
        "sections": [
            request_info("تاريخ الطلب"),
            client(False, "اسم العميل / الجهة المطلوب على عرض السعر"),
            address("عنوان الخدمة — إن تم تحديده", required=False),
            section(
                "تفاصيل الطلب",
                f("product_name", "اسم المنتج / الخدمة والنسخة", "product", True),
                f("quantity", "الكمية", "number", True, min=1, integer=True, default="1"),
                f("outlets", "عدد المخارج، إن ينطبق", "number", min=1, max=12, integer=True),
                f("cover_color", "لون الغطاء، إن يوجد", "select", options=COLORS),
                f("cooler_color", "لون البرادة، إن ينطبق", "select", options=COLORS),
                f("dimensions", "المقاسات المطلوبة، إن تنطبق"),
                f("design", "التصميم المطلوب / مرجع صورته"),
                f("addons", "الإضافات المطلوبة، إن وجدت", "textarea"),
                *INSCRIPTION,
                f("special_requirements", "مواصفات أو متطلبات خاصة", "textarea"),
            ),
            section(
                "قيمة الطلب",
                money("quoted_price", "السعر المطلوب عرضه، شامل الضريبة والإضافات، إن تم تحديده"),
                money("discount_amount", "قيمة الخصم المقترح، إن وجد"),
                f("discount_approved", "هل الخصم معتمد؟", "select", True, options=["نعم", "لا", "لا يوجد خصم"]),
                f("discount_approved_by", "اسم الشخص الذي اعتمد الخصم، إن تم", "staff",
                  required_if={"field": "discount_approved", "equals": "نعم"}),
            ),
            section(
                "شروط السداد المقترحة",
                f("payment_method", "طريقة الدفع", "select", options=PAYMENT_METHODS),
                f("advance_payment", "قيمة / نسبة الدفعة المقدمة"),
                f("remaining_due", "موعد سداد المتبقي"),
                f("payment_terms", "أي شروط سداد خاصة", "textarea"),
            ),
            attachments(
                files("design_image", "صورة المنتج أو التصميم المطلوب، إن توفرت"),
                files("inscription_file", "صورة / ملف الكتابة، إن وجدت"),
                files("specification_file", "ملف مواصفات أو طلب الجهة، إن وجد"),
            ),
            NOTES,
        ],
    },
    "quote_to_invoice": {
        "label": "طلب تحويل عرض سعر إلى فاتورة",
        "sections": [
            request_info(),
            client(False, "اسم العميل / الجهة المطلوب على الفاتورة"),
            address("عنوان الخدمة — إذا تغيّر أو لم يُذكر في العرض", required=False),
            section(
                "تفاصيل الطلب",
                f("quotation_number", "رقم عرض السعر المطلوب تحويله", required=True),
                f("quotation_date", "تاريخ عرض السعر", "date", True, not_future=True),
                f("product_name", "المنتج / الخدمة المرتبط بها العرض", "product", True),
                yes_no("customer_approved", "هل العميل وافق على عرض السعر؟"),
                f("approval_date", "تاريخ موافقة العميل، إن تم", "date", not_future=True,
                  required_if={"field": "customer_approved", "equals": "نعم"}),
                yes_no("has_changes", "هل يوجد تغيير عن العرض؟"),
                f("change_details", "تفاصيل التغيير، إن وجد", "textarea",
                  required_if={"field": "has_changes", "equals": "نعم"}),
                f("conversion_approved_by", "اسم المسؤول الذي اعتمد التحويل، إن تم", "staff"),
                yes_no("statement_needed", "هل مطلوب إرسال كشف حساب؟"),
            ),
            amounts(discount_label="خصم إضافي عن عرض السعر، إن وجد"),
            payment("تفاصيل الدفعة — إن وُجدت دفعة", when=PAID),
            attachments(
                files("quotation_file", "عرض السعر المطلوب تحويله", True),
                files("approval_proof", "إثبات موافقة العميل، إن توفر"),
                files("payment_proof", "إثبات الدفع، إن وُجدت دفعة", required_if=PAID),
                files("design_image", "التصميم أو المواصفات المعدّلة، إن وجدت"),
            ),
            NOTES,
        ],
    },
    "order_addition": {
        "label": "طلب إضافة على طلب قائم",
        "sections": [
            request_info(),
            client(True),
            address(),
            section(
                "تفاصيل الطلب",
                *original_refs(),
                f("product_name", "المنتج / الخدمة المرتبط بها الإضافة", "product", True),
                f("addition_details", "الإضافة المطلوبة بالتفصيل", "textarea", True),
                f("quantity_unit", "الكمية / الطول والوحدة", required=True),
                money("unit_price", "سعر الوحدة المتفق عليه، إن ينطبق"),
                f("specifications", "اللون / المقاسات / المواصفات، إن تنطبق"),
                *INSCRIPTION,
                yes_no("customer_approved", "هل العميل وافق على مواصفات الإضافة وتكلفتها؟"),
                f("addition_status", "حالة الإضافة", "select", True, options=WORK_STATUS),
                f("execution_info", "تاريخ التنفيذ واسم الفني، إن تم",
                  required_if={"field": "addition_status", "in": WORK_STARTED}),
            ),
            amounts(
                total_label="قيمة الإضافة النهائية بعد الخصم، شامل الضريبة",
                discount_label="قيمة الخصم على الإضافة، إن وجد",
                paid_label="المبلغ المدفوع فعليًا الآن مقابل الإضافة",
                remaining_label="المبلغ المتبقي من قيمة الإضافة",
            ),
            payment(when=PAID),
            attachments(
                files("payment_proof", "إثبات الدفع، إن وُجدت دفعة", required_if=PAID),
                files("invoice_image", "صورة الفاتورة / الطلب الأصلي، إن توفرت"),
                files("design_image", "صورة التصميم أو الإضافة المتفق عليها، إن توفرت"),
                files("inscription_file", "صورة / ملف الكتابة، إن وجدت"),
            ),
            NOTES,
        ],
    },
    "order_modification": {
        "label": "طلب تعديل على طلب قائم",
        "sections": [
            request_info(),
            client(True),
            address("عنوان الخدمة — إذا كان التعديل يخص العنوان", required=False),
            section(
                "تفاصيل الطلب",
                *original_refs(),
                f("product_name", "المنتج / الخدمة المرتبط بها التعديل", "product", True),
                f("modified_items", "المطلوب تعديله", "multiselect", True,
                  options=["بيانات العميل", "العنوان", "المنتج", "الكمية", "اللون", "التصميم", "الكتابة", "السعر", "أخرى"]),
                f("before_change", "البيانات أو المواصفات قبل التعديل", "textarea", True),
                f("after_change", "البيانات أو المواصفات المطلوبة بعد التعديل", "textarea", True),
                f("change_reason", "سبب التعديل", "textarea", True),
                f("execution_status", "حالة تنفيذ الطلب", "select", True,
                  options=["لم يبدأ", "قيد التنفيذ", "تم التنفيذ", "غير معروف"]),
                yes_no("customer_approved", "هل العميل وافق على التعديل وتكلفته؟"),
                f("change_approved_by", "اسم المسؤول الذي اعتمد التعديل، إن تم اعتماده", "staff"),
            ),
            section(
                "قيمة الطلب",
                f("value_change", "هل التعديل يغيّر قيمة الطلب؟", "select", True,
                  options=["زيادة", "تخفيض", "بدون تغيير", "تحتاج مراجعة"]),
                money("total_before", "قيمة الطلب النهائية قبل التعديل", True),
                money("total_amount", "قيمة الطلب النهائية بعد التعديل، شامل الضريبة والإضافات", True),
                *discount_fields("خصم إضافي مرتبط بالتعديل، إن وجد"),
                money("paid_amount", "المبلغ المدفوع فعليًا الآن", True),
                money("remaining_amount", "المبلغ المتبقي بعد التعديل", True),
                f("remaining_due_date", "موعد سداد المتبقي، إن وجد", "date"),
            ),
            payment("تفاصيل الدفعة — إن وُجدت دفعة جديدة", when=PAID),
            attachments(
                files("invoice_image", "صورة الفاتورة / الطلب الأصلي، إن توفرت"),
                files("design_image", "صورة التصميم أو المواصفات الجديدة، إن تنطبق"),
                files("inscription_file", "صورة / ملف الكتابة الجديدة، إن وجدت"),
                files("payment_proof", "إثبات الدفع، إن وُجدت دفعة جديدة", required_if=PAID),
            ),
            NOTES,
        ],
    },
    "return_refund": {
        "label": "طلب مرتجع ورد مبلغ",
        "sections": [
            request_info(),
            client(True),
            address("عنوان الخدمة / استلام المرتجع"),
            section(
                "تفاصيل الطلب",
                *original_refs(),
                f("return_type", "نوع المرتجع", "select", True, options=["كامل الطلب", "جزء من الطلب"]),
                f("returned_items", "المنتج / الأصناف المطلوب إرجاعها", "textarea", True),
                f("returned_quantities", "الكمية المرتجعة من كل صنف", "textarea", True),
                f("return_reason", "سبب المرتجع", "textarea", True),
                f("product_condition", "حالة المنتج وملاحظات عليه", "textarea", True),
                f("receipt_status", "حالة استلام المرتجع", "select", True, options=["لم يُستلم", "تم الاستلام"]),
                f("receipt_date", "تاريخ الاستلام، إن تم", "date", not_future=True,
                  required_if={"field": "receipt_status", "equals": "تم الاستلام"}),
                f("received_by", "اسم الموظف الذي استلم المرتجع، إن تم", "staff",
                  required_if={"field": "receipt_status", "equals": "تم الاستلام"}),
                f("return_approved_by", "اسم المسؤول الذي اعتمد المرتجع، إن تم اعتماده", "staff"),
            ),
            section(
                "قيمة الطلب",
                money("invoice_total", "قيمة الطلب النهائية المسجلة على الفاتورة", True),
                money("total_paid", "إجمالي المبلغ المدفوع على الطلب الأصلي", True),
                money("returned_value", "قيمة الأصناف المرتجعة حسب الفاتورة", True),
                money("deduction_amount", "قيمة أي استقطاع أو رسوم مرتبطة بالمرتجع، إن وجدت"),
                f("deduction_reason", "سبب الاستقطاع واسم المسؤول الذي اعتمده",
                  required_if={"field": "deduction_amount", "gt": 0}),
                money("approved_refund", "المبلغ المعتمد رده للعميل، إن تم تحديده"),
                f("refund_approved_by", "اسم المسؤول الذي اعتمد مبلغ الرد", "staff",
                  required_if={"field": "approved_refund", "gt": 0}),
                money("refunded_amount", "المبلغ المردود فعليًا الآن", True),
                f("refund_remaining", "المبلغ المتبقي من مبلغ الرد المعتمد", "number", money=True,
                  computed=["approved_refund", "refunded_amount"],
                  negative_message="المبلغ المردود أكبر من مبلغ الرد المعتمد"),
                f("refund_remaining_date", "موعد رد المتبقي، إن تم تحديده", "date"),
            ),
            section(
                "تفاصيل رد المبلغ — إن تم",
                f("refund_method", "طريقة رد المبلغ", "select", options=REFUND_METHODS,
                  required_if={"field": "refunded_amount", "gt": 0}),
                f("refund_date", "تاريخ رد المبلغ", "date", not_future=True,
                  required_if={"field": "refunded_amount", "gt": 0}),
                f("refund_reference", "رقم التحويل / مرجع عملية الرد / السند",
                  required_if={"field": "refunded_amount", "gt": 0}),
                f("refund_paid_by", "اسم الموظف الذي سلّم المبلغ، في حالة الرد النقدي", "staff",
                  required_if={"field": "refund_method", "equals": CASH}),
            ),
            attachments(
                files("invoice_image", "صورة الفاتورة الأصلية، إن توفرت"),
                files("product_photos", "صور المنتج المرتجع وحالته", True),
                files("receipt_proof", "إثبات استلام المرتجع، إن تم",
                      required_if={"field": "receipt_status", "equals": "تم الاستلام"}),
                files("refund_proof", "إثبات رد المبلغ، إن تم", required_if={"field": "refunded_amount", "gt": 0}),
            ),
            NOTES,
        ],
    },
    "tech_cash_collection": {
        "label": "تسجيل تحصيل نقدي بواسطة الفني",
        "sections": [
            request_info("تاريخ الطلب"),
            client(True, "اسم العميل"),
            section(
                "تفاصيل الطلب",
                f("invoice_number", "رقم الفاتورة المطلوب السداد عليها، إن توفر"),
                f("work_order", "رقم أمر الشغل، إن توفر"),
                f("collection_reason", "سبب التحصيل", "select", True, options=["باقي فاتورة", "أعمال إضافية", "أخرى"]),
                f("product_name", "المنتج / الخدمة المرتبط بها التحصيل", "product", True),
            ),
            section(
                "قيمة الطلب",
                money("paid_amount", "المبلغ المحصل نقدًا الآن", True, positive=True),
                f("amount_distribution", "توزيع المبلغ على الفواتير / الأسباب، إن شمل أكثر من فاتورة أو سبب", "textarea"),
            ),
            section(
                "تفاصيل الدفعة",
                f("payment_method", "طريقة الدفع", "select", True, options=[CASH], default=CASH),
                f("payment_date", "تاريخ الدفع", "date", True, default="today", not_future=True),
                f("paper_receipt_number", "رقم سند القبض الورقي", required=True),
                f("technician_name", "اسم الفني المحصل", "staff", required=True),
            ),
            attachments(
                files("receipt_image", "صورة سند القبض الورقي", True),
                files("invoice_image", "صورة الفاتورة المرتبطة، إن توفرت"),
            ),
            NOTES,
        ],
    },
    # ---------- Drafted from the design's form catalog; fields to be confirmed by the business ----------
    "reinstallation": {
        "label": "طلب إعادة تركيب",
        "sections": [
            request_info("تاريخ الطلب"),
            client(True, "اسم العميل"),
            address("عنوان التركيب الجديد"),
            section(
                "تفاصيل الطلب",
                *original_refs(),
                f("product_name", "المنتج / الجهاز المطلوب إعادة تركيبه", "product", True),
                f("reinstall_reason", "سبب إعادة التركيب", "select", True,
                  options=["نقل إلى عنوان جديد", "إعادة تركيب بعد صيانة", "تركيب سابق غير سليم", "أخرى"]),
                f("reason_details", "تفاصيل السبب", "textarea", True),
                f("current_location", "مكان الجهاز الحالي، إن اختلف عن العنوان الجديد"),
                f("preferred_date", "الموعد المفضل للتركيب", "date"),
                f("extra_works", "أعمال إضافية مطلوبة، إن وجدت (تمديدات، قاعدة، فك)", "textarea"),
            ),
            section(
                "قيمة الطلب",
                f("coverage", "تغطية الخدمة", "select", True, options=["مدفوعة", "مجانية / مشمولة", "تحتاج مراجعة"]),
                money("total_amount", "قيمة الخدمة شامل الضريبة", required_if={"field": "coverage", "equals": "مدفوعة"}),
                money("paid_amount", "المبلغ المدفوع فعليًا الآن"),
            ),
            payment(when=PAID),
            attachments(
                files("payment_proof", "إثبات الدفع، إن وُجدت دفعة", required_if=PAID),
                files("site_photos", "صور الموقع الجديد، إن توفرت"),
            ),
            NOTES,
        ],
    },
    "data_entry_error": {
        "label": "تبليغ خطأ إدخال بيانات",
        "sections": [
            request_info("تاريخ التبليغ"),
            client(False, "اسم العميل"),
            section(
                "تفاصيل الخطأ",
                f("document_type", "المستند الذي فيه الخطأ", "select", True,
                  options=["فاتورة", "سند قبض", "عرض سعر", "أمر شغل", "بيانات عميل", "أخرى"]),
                f("document_number", "رقم المستند", required=True),
                f("error_field", "البيان الخطأ (مثل: اسم العميل، المبلغ، التاريخ)", required=True),
                f("wrong_value", "القيمة المسجلة الخطأ", "textarea", True),
                f("correct_value", "القيمة الصحيحة", "textarea", True),
                f("urgency", "الأولوية", "select", True, options=["عادي", "عاجل"]),
            ),
            attachments(
                files("document_image", "صورة المستند الذي فيه الخطأ، إن توفرت"),
                files("evidence", "ما يثبت القيمة الصحيحة، إن توفر"),
            ),
            NOTES,
        ],
    },
    "pre_sale_inspection": {
        "label": "طلب معاينة قبل البيع",
        "sections": [
            request_info("تاريخ الطلب"),
            client(False, "اسم العميل / الجهة"),
            address("عنوان المعاينة"),
            section(
                "تفاصيل الطلب",
                f("site_type", "نوع الموقع", "select", True,
                  options=["منزل", "مسجد", "مدرسة", "مغسلة سيارات", "جمعية خيرية", "شركة", "أخرى"]),
                f("product_name", "المنتج المبدئي المهتم به العميل، إن وجد", "product"),
                f("inspection_purpose", "المطلوب من المعاينة", "textarea", True),
                f("preferred_date", "الموعد المفضل للمعاينة", "date"),
                f("preferred_time", "الوقت المفضل", "select", options=["صباحًا", "ظهرًا", "مساءً"]),
                f("site_contact", "اسم ورقم الشخص المسؤول في الموقع، إن اختلف عن العميل"),
            ),
            attachments(files("site_photos", "صور الموقع، إن توفرت")),
            NOTES,
        ],
    },
    "installation_completed": {
        "label": "تأكيد إتمام التركيب",
        "sections": [
            request_info("تاريخ الطلب"),
            client(True, "اسم العميل"),
            section(
                "تفاصيل التركيب",
                f("work_order", "رقم أمر الشغل", required=True),
                f("invoice_number", "رقم الفاتورة، إن توفر"),
                f("product_name", "المنتج الذي تم تركيبه", "product", True),
                f("installation_date", "تاريخ التركيب", "date", True, not_future=True),
                f("technician_name", "اسم الفني", "staff", required=True),
                f("installation_status", "حالة التركيب", "select", True, options=["تم بالكامل", "تم مع ملاحظات"]),
                f("issues", "الملاحظات على التركيب", "textarea",
                  required_if={"field": "installation_status", "equals": "تم مع ملاحظات"}),
                yes_no("extra_work", "هل نُفذت أعمال إضافية؟"),
                f("extra_work_details", "تفاصيل الأعمال الإضافية", "textarea", required_if={"field": "extra_work", "equals": "نعم"}),
                yes_no("customer_signed", "هل وقّع العميل على استلام التركيب؟"),
            ),
            section(
                "التحصيل عند التركيب",
                money("paid_amount", "المبلغ المحصل عند التركيب، إن وجد"),
                f("payment_method", "طريقة الدفع", "select", options=PAYMENT_METHODS, required_if=PAID),
                f("payment_reference", "رقم التحويل / السند الورقي", required_if=PAID),
            ),
            attachments(
                files("installation_photos", "صور التركيب بعد الانتهاء", True),
                files("signed_work_order", "صورة أمر الشغل الموقّع، إن توفرت"),
                files("payment_proof", "إثبات الدفع، إن وُجد تحصيل", required_if=PAID),
            ),
            NOTES,
        ],
    },
    "contract_service_done": {
        "label": "تأكيد إنجاز خدمة مشمولة بالعقد",
        "sections": [
            request_info("تاريخ الطلب"),
            client(True, "اسم العميل"),
            section(
                "تفاصيل الخدمة",
                f("contract_number", "رقم العقد / الفاتورة", required=True),
                f("visit_number", "رقم الزيارة في العقد", "select", True,
                  options=["الزيارة الأولى", "الزيارة الثانية", "الزيارة الثالثة", "الزيارة الرابعة", "زيارة إضافية"]),
                f("services_done", "الخدمات المنفذة", "multiselect", True,
                  options=["تبديل فلاتر", "صيانة البرادة", "تنظيف", "فحص"]),
                f("service_date", "تاريخ التنفيذ", "date", True, not_future=True),
                f("technician_name", "اسم الفني", "staff", required=True),
                f("parts", "القطع والفلاتر المستبدلة وكمياتها", "textarea"),
                f("cooler_notes", "ملاحظات على حالة البرادة، إن وجدت", "textarea"),
                f("next_visit_date", "موعد الزيارة القادمة، إن تحدد", "date"),
            ),
            attachments(
                files("service_photos", "صور قبل وبعد الخدمة، إن توفرت"),
                files("signed_report", "تقرير الزيارة الموقّع، إن توفر"),
            ),
            NOTES,
        ],
    },
    "open_ticket": {
        "label": "فتح بلاغ صيانة وأعطال",
        "sections": [
            request_info("تاريخ البلاغ"),
            client(False, "اسم العميل"),
            address(),
            section(
                "تفاصيل البلاغ",
                f("device_type", "الجهاز / البرادة", required=True),
                f("related_number", "رقم العقد أو الفاتورة المرتبطة، إن توفر"),
                f("problem", "وصف العطل كما ذكره العميل", "textarea", True),
                f("coverage", "تغطية الإصلاح", "select", True, options=["ضمان", "عقد صيانة", "مدفوع", "غير معروف"]),
                f("urgency", "الأولوية", "select", True, options=["عادي", "عاجل", "طارئ"]),
                f("preferred_date", "الموعد المفضل للزيارة، إن وجد", "date"),
            ),
            attachments(files("fault_media", "صور / فيديو العطل، إن توفرت")),
            NOTES,
        ],
    },
    "close_ticket": {
        "label": "إغلاق بلاغ صيانة وأعطال",
        "sections": [
            request_info("تاريخ الإغلاق"),
            client(True, "اسم العميل"),
            section(
                "تفاصيل الإغلاق",
                f("ticket_number", "رقم البلاغ / الطلب الأصلي", required=True),
                f("visit_date", "تاريخ الزيارة", "date", True, not_future=True),
                f("technician_name", "اسم الفني", "staff", required=True),
                f("resolution", "نتيجة الزيارة", "select", True,
                  options=["تم الإصلاح", "تم استبدال قطع", "يحتاج زيارة أخرى", "تعذر الإصلاح"]),
                f("work_details", "الأعمال المنفذة بالتفصيل", "textarea", True),
                f("parts", "القطع المستبدلة وكمياتها، إن وجدت", "textarea"),
                f("follow_up_date", "موعد الزيارة التالية", "date", required_if={"field": "resolution", "equals": "يحتاج زيارة أخرى"}),
            ),
            section(
                "قيمة الطلب",
                f("coverage", "تغطية الإصلاح", "select", True, options=["مشمول بعقد أو ضمان", "مدفوع"]),
                money("total_amount", "قيمة الإصلاح شامل الضريبة", required_if={"field": "coverage", "equals": "مدفوع"}),
                money("paid_amount", "المبلغ المدفوع فعليًا الآن"),
            ),
            payment(when=PAID),
            attachments(
                files("after_photos", "صور بعد الإصلاح، إن توفرت"),
                files("payment_proof", "إثبات الدفع، إن وُجدت دفعة", required_if=PAID),
            ),
            NOTES,
        ],
    },
    "daily_visits": {
        "label": "تقرير الزيارات اليومي",
        "sections": [
            section(
                "بيانات التقرير",
                f("request_date", "تاريخ التقرير", "date", True, default="today", not_future=True),
                f("employee_name", "اسم الموظف", "auto_user"),
                f("visit_area", "المنطقة / خط السير"),
            ),
            section(
                "الزيارات",
                f("visits_count", "عدد الزيارات", "number", True, min=1, integer=True),
                f("visits", "تفاصيل الزيارات: لكل زيارة سطر فيه العميل والمنطقة والغرض والنتيجة", "textarea", True, max_length=6000),
                f("new_leads", "عدد العملاء المهتمين الجدد", "number", min=0, integer=True),
                f("closed_sales", "عدد المبيعات المؤكدة", "number", min=0, integer=True),
                money("collected_amount", "إجمالي المبالغ المحصلة، إن وجدت"),
                f("issues", "مشاكل أو طلبات تحتاج متابعة", "textarea"),
            ),
            attachments(files("visit_photos", "صور من الزيارات، إن توفرت")),
            NOTES,
        ],
    },
    "tech_extra_works": {
        "label": "اعمال اضافية (قسم الفنيات)",
        # Approving it invoices the extra works to a client Daftra already has, and makes the receipt
        # for whatever was paid now. No address is asked for, so no client can be created here.
        "invoiced": True,
        "daftra_note": "وتُنشأ في دفترة فاتورة الأعمال المختارة، وسند القبض إن وُجدت دفعة. العميل يجب أن يكون مسجلًا في دفترة.",
        "sections": [
            # The technical department does not always know which source the work came through
            request_info("تاريخ الطلب", invoiced=True, source_required=False),
            client(False),
            section(
                "تفاصيل الطلب",
                # Only the technical department's services, by their Daftra product id. «أخرى» is
                # described and priced on its own line, and can be added more than once.
                f("order_lines", "الأعمال المطلوبة", "order_lines", True, subtotal_field="total_amount",
                  items="tech_services", item_ids=TECH_SERVICE_DAFTRA_IDS, item_labels=TECH_SERVICE_LABELS,
                  line_fields=[
                      f("work_description", "وصف العمل", "text", True, max_length=500,
                        only_for=[OTHER_WORK_DAFTRA_ID]),
                      money("work_price", "سعر الوحدة، شامل الضريبة (درهم)", True, positive=True,
                            only_for=[OTHER_WORK_DAFTRA_ID], line_price=True),
                  ]),
                # Printed on the invoice as «الفني: …», which is how the technical department finds
                # its own work again in Daftra
                f("technician", "الفني (الموظف في دفترة)", "daftra_staff", True),
            ),
            amounts(total_label="قيمة الأعمال النهائية، شامل الضريبة", auto_total=True, invoiced=False,
                    paid_label="المبلغ المدفوع فعليًا الآن", discounts=False),
            payment(when=PAID, invoiced=True),
            NOTES,
        ],
    },
}


# The forms a new request can be made from. The others stay defined (requests already made with
# them still open, show and can be reviewed) but are hidden; add a key here to bring one back.
VISIBLE_FORM_TYPES = {"new_sale", "contract_renewal", "balance_payment", "maintenance", "tech_extra_works"}


def list_form_types() -> list[dict]:
    return [{"key": key, **definition, "hidden": key not in VISIBLE_FORM_TYPES} for key, definition in FORM_TYPES.items()]


def form_fields(form_type: str) -> list[dict]:
    return [spec for s in FORM_TYPES[form_type]["sections"] for spec in s["fields"]]
