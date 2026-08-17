// Assertions for ui/js/core/utils.js, run against a minimal DOM stub.
//
//   node tests/check_ui_utils.js
//
// The frontend has no build step and no test runner, and these helpers are
// shared by every dashboard tab, so this is the cheapest way to catch a
// regression in them. Node built-ins only — nothing to install.
const fs = require('fs'), assert = require('assert'), vm = require('vm'), path = require('path');

const sandbox = {
  document: { getElementById: () => null },
  setInterval: () => 0,
  fetch: () => Promise.resolve({ json: () => ({}) }),
  Date, String, Number, Math, JSON, Set,
};
sandbox.window = sandbox;
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(path.join(__dirname, '..', 'ui', 'js', 'core', 'utils.js'), 'utf8'), sandbox);
const w = sandbox;

// avatarHtml: default base class, size modifier, and escaping
assert.strictEqual(w.avatarHtml('Naimi Nafis', 0),
  '<div class="avatar av-teal">NN</div>');
assert.strictEqual(w.avatarHtml('Naimi Nafis', 1, 'avatar avatar-lg'),
  '<div class="avatar avatar-lg av-blue">NN</div>');
assert.strictEqual(w.avatarHtml('Naimi Nafis', 0, 'picker-av'),
  '<div class="picker-av av-teal">NN</div>');
// The escaping gap this closes: two old call sites inlined initials unescaped.
assert.ok(!w.avatarHtml('<script>x</script> Bad', 0).includes('<s'),
  'initials must be HTML-escaped');

// avColor rotates over 5 colours
assert.strictEqual(w.avColor(5), w.avColor(0));

// isoDate is local time, NOT toISOString (which would roll back a day in JST)
const morning = new Date(2026, 4, 20, 8, 30);   // 2026-05-20 08:30 local
assert.strictEqual(w.isoDate(morning), '2026-05-20');
assert.strictEqual(w.isoDate(new Date(2026, 0, 5)), '2026-01-05', 'zero-padding');

// mondayOf snaps back to Monday 00:00 and is idempotent
const wed = new Date(2026, 4, 20, 15, 0);       // Wednesday
const mon = w.mondayOf(wed);
assert.strictEqual(w.isoDate(mon), '2026-05-18');
assert.strictEqual(mon.getHours(), 0);
assert.strictEqual(w.isoDate(w.mondayOf(mon)), '2026-05-18', 'idempotent');
assert.strictEqual(w.isoDate(w.mondayOf(new Date(2026, 4, 24))), '2026-05-18', 'Sunday belongs to the prior Monday');

// byPresenceThenName: present first, then alphabetical
const sorted = [
  { name: 'Zoe', status: true }, { name: 'Adam', status: false },
  { name: 'Bob', status: true },
].sort(w.byPresenceThenName).map(u => u.name);
assert.deepStrictEqual(sorted, ['Bob', 'Zoe', 'Adam']);

// fmtMins still fine
assert.strictEqual(w.fmtMins(125), '2h 5m');
assert.strictEqual(w.fmtMins(45), '45m');

// dead helpers are gone
assert.strictEqual(w.isStudent, undefined, 'isStudent was dead');
assert.strictEqual(w.isTeacher, undefined, 'isTeacher is internal now');
assert.strictEqual(typeof w.roleBadgeClass('先生'), 'string');
assert.strictEqual(w.roleBadgeClass('先生'), 'badge-admin');
assert.strictEqual(w.roleBadgeClass('卒業'), 'badge-grad');
assert.strictEqual(w.roleBadgeClass('M1'), 'badge-student');

console.log('ui/js/core/utils.js: all assertions passed');
