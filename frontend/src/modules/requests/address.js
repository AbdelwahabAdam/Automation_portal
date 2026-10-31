// How التصنيف, المنطقة and الإمارة follow each other. Picking a التصنيف sets the other two; a known
// المنطقة sets its الإمارة; and each narrows what the ones below it offer. Whatever no longer belongs
// after a change is emptied rather than left to reach Daftra mismatched.
//
// المنطقة is typed: it usually holds a neighbourhood («الخوانيج 2») that no list knows, so only the
// regions in the form's list can say where they are. A neighbourhood sets nothing and clears nothing.

const NO_CATEGORY = { category: '', category_name: '' };

export const categoryById = (categories, id) => categories?.find((row) => String(row.id) === String(id));

// The emirate of a region of the form's list; undefined for anything else
export const emirateOfArea = (areasByEmirate, area) => Object.keys(areasByEmirate || {})
  .find((emirate) => areasByEmirate[emirate].includes(area));

// The categories to offer: those of the area, else of the emirate, else all of them. An area with
// none of its own says nothing, so it falls back to the emirate instead of an empty list. The one
// already chosen stays, or the list could not show it (a found client's own, from Daftra).
export function categoriesFor(categories, { emirate, area }, chosenId) {
  if (!categories) return categories;
  const inArea = area ? categories.filter((row) => row.area === area) : [];
  const shown = inArea.length ? inArea : emirate ? categories.filter((row) => row.emirate === emirate) : categories;
  const chosen = categoryById(categories, chosenId);
  return chosen && !shown.includes(chosen) ? [chosen, ...shown] : shown;
}

// What picking a التصنيف changes. One that does not say where its clients are changes nothing.
export const afterCategory = (row) => (row?.area && row?.emirate ? { area: row.area, emirate: row.emirate } : {});

// What typing or picking an المنطقة changes
export function afterArea(values, area, { areasByEmirate, categories }) {
  const emirate = emirateOfArea(areasByEmirate, area);
  if (!emirate) return { area };
  const category = categoryById(categories, values.category);
  return { area, emirate, ...(category?.area && category.area !== area ? NO_CATEGORY : {}) };
}

// What picking a الإمارة changes. A neighbourhood stays: nothing says it is in another emirate.
export function afterEmirate(values, emirate, { areasByEmirate, categories }) {
  if (!emirate) return { emirate };
  const category = categoryById(categories, values.category);
  const areaEmirate = emirateOfArea(areasByEmirate, values.area);
  return {
    emirate,
    ...(category?.emirate && category.emirate !== emirate ? NO_CATEGORY : {}),
    ...(areaEmirate && areaEmirate !== emirate ? { area: '' } : {}),
  };
}
