// Matching typed text against a list, forgiving the ways Arabic is spelled.
// Used by every search box and by the dropdowns in index.jsx.

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

// Whether two written names can be the same person: «محمد سعيد» and «محمد سعيد سهيل», «حمد السنانى» and
// «حمد السناني», but not «حمد يوسف محمد السناني» and «محمد سعيد سهيل». Lenient, as the server's
// clients.same_person is, with the same rule: the same once spelling is put aside, or every word of
// the shorter in the longer, or the same first two words. A name missing on either side is no difference.
export function samePerson(name, other) {
  const [a, b] = [name, other].map((text) => normalize(text).split(' ').filter(Boolean));
  if (!a.length || !b.length) return true;
  const [joinedA, joinedB] = [a.join(''), b.join('')];
  const [shorter, longer] = a.length <= b.length ? [a, b] : [b, a];
  return joinedA.includes(joinedB) || joinedB.includes(joinedA)
    || shorter.every((word) => longer.includes(word))
    || (a[0] === b[0] && a[1] === b[1]);
}
