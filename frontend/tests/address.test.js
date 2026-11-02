// node --test tests/  How التصنيف, المنطقة and الإمارة follow and narrow each other.
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { afterCategory, afterEmirate, areaOf, categoriesFor } from '../src/modules/requests/address.js';

const AIN = { id: 1, name: 'العين العامره', emirate: 'أبوظبي', area: 'منطقة العين' };
const ABU_DHABI = { id: 2, name: 'الشامخه', emirate: 'أبوظبي', area: 'منطقة أبوظبي' };
const DUBAI = { id: 3, name: 'المزهر', emirate: 'دبي', area: 'مدينة دبي' };
const NOWHERE = { id: 4, name: 'لم يتم التركيب', emirate: null, area: null };
const categories = [AIN, ABU_DHABI, DUBAI, NOWHERE];
const lists = { categories };
const ids = (rows) => rows.map((row) => row.id);

test('nothing chosen offers every category', () => {
  assert.deepEqual(ids(categoriesFor(categories, {})), [1, 2, 3, 4]);
  assert.equal(categoriesFor(undefined, {}), undefined);
});

test('an emirate offers only its own categories', () => {
  assert.deepEqual(ids(categoriesFor(categories, { emirate: 'أبوظبي' })), [1, 2]);
});

test('the area does not narrow them: it comes from the category, not the other way round', () => {
  assert.deepEqual(ids(categoriesFor(categories, { emirate: 'أبوظبي', area: 'منطقة العين' })), [1, 2]);
});

test('the chosen category stays in the list even where it does not belong', () => {
  assert.deepEqual(ids(categoriesFor(categories, { emirate: 'دبي' }, 1)), [1, 3]);
  assert.deepEqual(ids(categoriesFor(categories, { emirate: 'دبي' }, '3')), [3]);
});

test('picking a category names the area after it and sets its emirate', () => {
  assert.deepEqual(afterCategory(DUBAI), { area: 'المزهر', emirate: 'دبي' });
});

test('a category that does not say where it is still names the area, and leaves the emirate', () => {
  assert.deepEqual(afterCategory(NOWHERE), { area: 'لم يتم التركيب' });
});

test('no category changes nothing', () => {
  assert.deepEqual(afterCategory(undefined), {});
});

test('the area is the category, whatever the client\'s address on file says', () => {
  assert.equal(areaOf({ category: '3', category_name: 'المزهر', area: 'مدينة دبي' }, categories), 'المزهر');
});

test('the category\'s name in the list decides, over the one saved with it', () => {
  assert.equal(areaOf({ category: '3', category_name: 'اسم قديم' }, categories), 'المزهر');
});

test('a client\'s category that is not on the list still names the area', () => {
  assert.equal(areaOf({ category: '99', category_name: 'تصنيف العميل' }, categories), 'تصنيف العميل');
  assert.equal(areaOf({ category: '3', category_name: 'المزهر' }, undefined), 'المزهر');
});

test('with no category there is no area', () => {
  assert.equal(areaOf({ category: '', area: 'منطقة العين' }, categories), '');
  assert.equal(areaOf({}, categories), '');
});

test('a category not known by name yet has no area to give', () => {
  assert.equal(areaOf({ category: '99' }, undefined), '');
});

test('a category with no place of its own survives a change of emirate', () => {
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
