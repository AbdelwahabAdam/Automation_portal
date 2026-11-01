// How التصنيف, المنطقة and الإمارة follow each other.
//
// المنطقة is not the user's to set: it is the التصنيف picked, so the client reaches Daftra with its
// category and its المنطقة saying the same thing. The backend fills it in again from what is sent
// (a field's from_category), so the two can never disagree.
//
// The one link left is between التصنيف and الإمارة: picking a التصنيف sets the الإمارة its clients are
// in, and picking an الإمارة narrows the categories offered and drops one that is somewhere else.

const NO_CATEGORY = { category: '', category_name: '' };

export const categoryById = (categories, id) => categories?.find((row) => String(row.id) === String(id));

// The categories to offer: those of the الإمارة, else all of them. The one already chosen stays,
// or the list could not show it (a found client's own, from Daftra).
export function categoriesFor(categories, { emirate }, chosenId) {
  if (!categories) return categories;
  const shown = emirate ? categories.filter((row) => row.emirate === emirate) : categories;
  const chosen = categoryById(categories, chosenId);
  return chosen && !shown.includes(chosen) ? [chosen, ...shown] : shown;
}

// What picking a التصنيف changes: المنطقة is its own name, and الإمارة is where its clients are.
// One that does not say where they are still gives its name to المنطقة.
export const afterCategory = (row) => (row ? { area: row.name, ...(row.emirate ? { emirate: row.emirate } : {}) } : {});

// What picking a الإمارة changes: a التصنيف of another الإمارة is dropped, and المنطقة goes with it.
export function afterEmirate(values, emirate, { categories }) {
  if (!emirate) return { emirate };
  const category = categoryById(categories, values.category);
  const gone = category?.emirate && category.emirate !== emirate;
  return { emirate, ...(gone ? { ...NO_CATEGORY, area: '' } : {}) };
}
