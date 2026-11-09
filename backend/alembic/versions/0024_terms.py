"""الشروط والأحكام become data: versioned texts, and which one each package prints.

Until now every invoice the portal created printed the warranty terms (WARRANTY_TERMS_HTML in
invoicing/invoice.py). From now on an invoice or estimate prints the term of the first package
added to the request that has one (chosen in the package's editor), and none otherwise.

The text every invoice printed until now is added as «شروط وأحكام الضمان» version 1, but no
package is given it: until packages are, invoices print no terms.

Each request also keeps which term its invoice printed (printed_terms_id, and its name and
version as printed).
"""

import sqlalchemy as sa
from alembic import op

revision = "0024"
down_revision = "0023"

WARRANTY_NAME = "شروط وأحكام الضمان"
WARRANTY_BODY = 'شروط وأحكام الضمان\n\n1. يقرّ العميل باستلام الجهاز / براد المياه بحالة سليمة وجيدة وصالحة للتشغيل.\n\n2. مدة الضمان سنة واحدة من تاريخ الفاتورة، ويشمل عيوب التصنيع فقط، ما لم يُنص على خلاف ذلك في بنود خاصة.\n\n3. لا يشمل الضمان الأجزاء الاستهلاكية مثل صنبور المياه، حاوية الفلتر، والفلاتر، إلا إذا تم النص صراحة على خلاف ذلك.\n\n4. ضمان الكمبروسر ثلاث (3) سنوات من تاريخ الفاتورة، ويشمل عيوب التصنيع فقط.\n\n5. لا يشمل ضمان الكمبروسر برادة الطعام (إن وُجدت)، ويكون ضمان كمبروسر برادة الطعام سنة واحدة فقط من تاريخ الفاتورة.\n\n6. أي فتح أو تعديل أو عبث غير مصرح به بأي جزء من أجزاء الجهاز، بما في ذلك الصنبور، الجسم الخلفي، الغطاء العلوي، أوالتوصيلات الداخلية، يؤدي إلى إلغاء الضمان فورًا .\n\n7. يتحمل العميل كامل المسؤولية عن استخراج أي تصاريح أو موافقات لازمة لتوصيلات المياه والكهرباء، ولا تتحمل شركة المستقبل لايف أي مسؤولية عن الاستخدام غير المصرح به أو أي رسوم أو مخالفات ناتجة عن ذلك.\n\n8. تتحمل شركة المستقبل لايف أعمال التوريد والتركيب، بما يشمل تمديدات المياه والكهرباء، بشرط ألا تتجاوز مسافة التمديدات (15) مترًا.\n\n9. في حال زيادة مسافة التمديدات عن (15) مترًا، يتم احتساب تكلفة إضافية على النحو التالي:\n\n• 6 دراهم لكل متر لتمديدات المياه.\n• 7 دراهم لكل متر لتمديدات الكهرباء.\n\n10. يغطي الضمان عيوب التصنيع فقط، ولا يشمل الأعطال أو الأضرار الناتجة عن سوء الاستخدام، الإهمال، الحوادث، الكوارث الطبيعية، التشغيل غير الصحيح، أو النقل غير المعتمد للجهاز.\n\n11. لا يشمل الضمان أي نقل أو تحريك غير منظم أو غير مصرح به للجهاز من مكان إلى آخر.\n\n12. في حال وجود شكوى أو عطل، يتم الاستجابة والرد خلال يومي عمل من تاريخ استلام البلاغ.\n\n13. في حال طلب صيانة وتبيّن عند وصول فريق الصيانة أن الجهاز يعمل بحالة طبيعية، وأن العطل ناتج عن سوء استخدام أو خطأ من جهة العميل، يتحمل العميل تكلفة الزيارة، ويتم تحديدها حسب الإمارة.\n\n14. عند تركيب أو إضافة أي أجزاء أو ملحقات داخل أو خارج الجهاز تؤدي إلى تلف أي جزء من أجزائه، يتحمل العميل كامل تكلفة الإصلاح حتى وإن كان الجهاز ضمن فترة الضمان.\n\n15. تحتفظ شركة المستقبل لايف بحق تعديل أو تحديث هذه الشروط والأحكام عند الحاجة، ويُعمل بالتعديلات من تاريخ اعتمادها أو نشرها رسميًا.\n\nتمديد ضمان الكمبروسر\n\nيمكن تمديد ضمان الكمبروسر حتى خمس (5) سنوات من تاريخ الفاتورة، وذلك عند توقيع عقد صيانة مع شركة المستقبل لايف وفق الشروط المعتمدة في عقد الصيانة'


def upgrade():
    op.create_table(
        "terms",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("created_by_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("name", "version", name="uq_terms_name_version"),
    )
    op.create_table(
        "package_terms",
        sa.Column("package_id", sa.Integer, sa.ForeignKey("packages.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("term_id", sa.Integer, sa.ForeignKey("terms.id", ondelete="RESTRICT"), nullable=False, index=True),
    )
    op.add_column("requests", sa.Column("printed_terms_id", sa.Integer,
                                        sa.ForeignKey("terms.id", ondelete="SET NULL"), nullable=True))
    op.create_index("ix_requests_printed_terms_id", "requests", ["printed_terms_id"])
    op.add_column("requests", sa.Column("printed_terms", sa.String(250), nullable=True))
    op.get_bind().execute(sa.text("INSERT INTO terms (name, version, body) VALUES (:name, 1, :body)"),
                          {"name": WARRANTY_NAME, "body": WARRANTY_BODY})


def downgrade():
    op.drop_index("ix_requests_printed_terms_id", table_name="requests")
    op.drop_column("requests", "printed_terms")
    op.drop_column("requests", "printed_terms_id")
    op.drop_table("package_terms")
    op.drop_table("terms")
