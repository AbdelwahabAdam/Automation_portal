// node --test tests/  How التصنيف, المنطقة and الإمارة follow and narrow each other.
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { afterArea, afterCategory, afterEmirate, categoriesFor } from '../src/modules/requests/address.js';

const AIN = { id: 1, name: 'العين العامره', emirate: 'أبوظبي', area: 'منطقة العين' };
const ABU_DHABI = { id: 2, name: 'الشامخه', emirate: 'أبوظبي', area: 'منطقة أبوظبي' };
const DUBAI = { id: 3, name: 'المزهر', emirate: 'دبي', area: 'مدينة دبي' };
const NOWHERE = { id: 4, name: 'لم يتم التركيب', emirate: null, area: null };
const categories = [AIN, ABU_DHABI, DUBAI, NOWHERE];
const lists = {
  categories,
  areasByEmirate: { أبوظبي: ['منطقة أبوظبي', 'منطقة العين'], دبي: ['مدينة دبي', 'حتا'] },
};
const ids = (rows) => rows.map((row) => row.id);

test('nothing chosen offers every category', () => {
  assert.deepEqual(ids(categoriesFor(categories, {})), [1, 2, 3, 4]);
  assert.equal(categoriesFor(undefined, {}), undefined);
});

test('an area offers only its own categories', () => {
  assert.deepEqual(ids(categoriesFor(categories, { emirate: 'أبوظبي', area: 'منطقة العين' })), [1]);
});

test('an emirate offers only its own categories', () => {
  assert.deepEqual(ids(categoriesFor(categories, { emirate: 'أبوظبي' })), [1, 2]);
});

test('a neighbourhood or an area with no categories falls back to the emirate, not an empty list', () => {
  assert.deepEqual(ids(categoriesFor(categories, { emirate: 'دبي', area: 'الخوانيج 2' })), [3]);
  assert.deepEqual(ids(categoriesFor(categories, { emirate: 'دبي', area: 'حتا' })), [3]);
});

test('the chosen category stays in the list even where it does not belong', () => {
  assert.deepEqual(ids(categoriesFor(categories, { emirate: 'دبي' }, 1)), [1, 3]);
  assert.deepEqual(ids(categoriesFor(categories, { emirate: 'دبي' }, '3')), [3]);
});

test('picking a category sets the area and the emirate; one that says nothing changes nothing', () => {
  assert.deepEqual(afterCategory(DUBAI), { area: 'مدينة دبي', emirate: 'دبي' });
  assert.deepEqual(afterCategory(NOWHERE), {});
  assert.deepEqual(afterCategory(undefined), {});
});

test('a known area sets its emirate', () => {
  assert.deepEqual(afterArea({}, 'مدينة دبي', lists), { area: 'مدينة دبي', emirate: 'دبي' });
});

test('an area clears a category that belongs elsewhere, and keeps its own', () => {
  assert.deepEqual(afterArea({ category: '1' }, 'مدينة دبي', lists),
    { area: 'مدينة دبي', emirate: 'دبي', category: '', category_name: '' });
  assert.deepEqual(afterArea({ category: '3' }, 'مدينة دبي', lists), { area: 'مدينة دبي', emirate: 'دبي' });
});

test('typing a neighbourhood touches nothing else', () => {
  assert.deepEqual(afterArea({ category: '1', emirate: 'أبوظبي' }, 'الخوانيج 2', lists), { area: 'الخوانيج 2' });
});

test('a category with no place of its own survives a change of area or emirate', () => {
  assert.deepEqual(afterArea({ category: '4' }, 'مدينة دبي', lists), { area: 'مدينة دبي', emirate: 'دبي' });
  assert.deepEqual(afterEmirate({ category: '4' }, 'دبي', lists), { emirate: 'دبي' });
});

test('an emirate clears the category and region of another emirate', () => {
  assert.deepEqual(afterEmirate({ category: '1', area: 'منطقة العين' }, 'دبي', lists),
    { emirate: 'دبي', category: '', category_name: '', area: '' });
});

test('an emirate keeps what is inside it, and a neighbourhood', () => {
  assert.deepEqual(afterEmirate({ category: '1', area: 'منطقة العين' }, 'أبوظبي', lists), { emirate: 'أبوظبي' });
  assert.deepEqual(afterEmirate({ area: 'الخوانيج 2' }, 'دبي', lists), { emirate: 'دبي' });
});

test('emptying the emirate clears nothing else', () => {
  assert.deepEqual(afterEmirate({ category: '1', area: 'منطقة العين' }, '', lists), { emirate: '' });
});
