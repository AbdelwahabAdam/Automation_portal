// How each form type appears in the forms catalog: icon (design system set) and a one-line description.
// The form itself (fields, rules) is defined by the backend in backend/app/forms.py.
export const FORM_META = {
  new_sale: { icon: 'package', desc: 'تسجيل طلب بيع جديد' },
  contract_renewal: { icon: 'calendar', desc: 'تجديد عقد الصيانة' },
  maintenance: { icon: 'tool', desc: 'صيانة وتبديل فلاتر' },
  balance_payment: { icon: 'send', desc: 'سداد المبلغ المتبقي على طلب' },
  quotation: { icon: 'file-text', desc: 'تسجيل طلب عرض سعر' },
  quote_to_invoice: { icon: 'copy', desc: 'تحويل عرض سعر معتمد إلى فاتورة' },
  order_addition: { icon: 'plus', desc: 'تسجيل إضافة مرتبطة بطلب' },
  order_modification: { icon: 'edit', desc: 'تسجيل التعديل المطلوب' },
  return_refund: { icon: 'history', desc: 'تسجيل المرتجع ورد المبلغ' },
  tech_cash_collection: { icon: 'receipt', desc: 'تسجيل التحصيل النقدي' },
  reinstallation: { icon: 'refresh', desc: 'تسجيل طلب إعادة تركيب' },
  data_entry_error: { icon: 'alert-triangle', desc: 'مطلوب تصحيح' },
  pre_sale_inspection: { icon: 'eye', desc: 'تسجيل طلب معاينة' },
  installation_completed: { icon: 'check-circle', desc: 'تسجيل تأكيد الإتمام' },
  contract_service_done: { icon: 'shield', desc: 'تسجيل إنجاز الخدمة' },
  open_ticket: { icon: 'alert-circle', desc: 'تسجيل بلاغ جديد' },
  close_ticket: { icon: 'x-circle', desc: 'تسجيل إغلاق البلاغ' },
  daily_visits: { icon: 'map-pin', desc: 'تسجيل تقرير الزيارات' },
};

export const formMeta = (key) => FORM_META[key] || { icon: 'file', desc: '' };

// Search that forgives Arabic spelling variants: diacritics, tatweel, alef forms, ى/ي, ة/ه, punctuation
export function normalize(text) {
  return String(text ?? '')
    .toLowerCase()
    .replace(/[ً-ٰٟـ]/g, '')
    .replace(/[أإآٱ]/g, 'ا')
    .replace(/ى/g, 'ي')
    .replace(/ة/g, 'ه')
    .replace(/[٠-٩]/g, (d) => '٠١٢٣٤٥٦٧٨٩'.indexOf(d))
    .replace(/[^\p{L}\p{N}\s]/gu, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

// Every word of the query appears somewhere in the texts
export function matchesQuery(query, ...texts) {
  const words = normalize(query).split(' ').filter(Boolean);
  if (!words.length) return true;
  const haystack = normalize(texts.join(' '));
  return words.every((word) => haystack.includes(word));
}

// The day an ISO time falls on here (2026-10-21), for comparing with a date picker's value
export function localDay(iso) {
  if (!iso) return '';
  const at = new Date(iso);
  return new Date(at.getTime() - at.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}

export const formatDate = (iso) =>
  iso ? new Date(iso).toLocaleString('en-GB', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false }).replace(',', '') : '';

export const formatMoney = (value) => Number(value).toLocaleString('en-US', { maximumFractionDigits: 2 });
