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
