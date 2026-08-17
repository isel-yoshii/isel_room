// Assertions for ui/js/core/utils.js against a minimal DOM stub. The frontend
// has no build step and no test runner, so: node tests/check_ui.js
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

const sorted = [
  { name: 'Zoe', status: true }, { name: 'Adam', status: false },
  { name: 'Bob', status: true },
].sort(w.byPresenceThenName).map(u => u.name);
assert.deepStrictEqual(sorted, ['Bob', 'Zoe', 'Adam']);

assert.strictEqual(w.fmtMins(125), '2h 5m');
assert.strictEqual(w.fmtMins(45), '45m');

assert.strictEqual(w.isStudent, undefined, 'isStudent was dead');
assert.strictEqual(w.isTeacher, undefined, 'isTeacher is internal now');
assert.strictEqual(typeof w.roleBadgeClass('先生'), 'string');
assert.strictEqual(w.roleBadgeClass('先生'), 'badge-admin');
assert.strictEqual(w.roleBadgeClass('卒業'), 'badge-grad');
assert.strictEqual(w.roleBadgeClass('M1'), 'badge-student');

console.log('ui/js/core/utils.js: all assertions passed');

// closeModalOnBg: overlay clicks only, never clicks bubbling up from content.
{
  const overlay = { id: 'reg-modal' }, content = { id: 'reg-body' };
  let closed = 0;
  w.closeModalOnBg({ target: overlay, currentTarget: overlay }, () => closed++);
  assert.strictEqual(closed, 1, 'backdrop click closes');
  w.closeModalOnBg({ target: content, currentTarget: overlay }, () => closed++);
  assert.strictEqual(closed, 1, 'click inside the modal must not close it');
}

// All five kiosk states go through one table, so a regression here breaks the
// door screen. These pin the rendered shape and the escaping.
const IDS = ['state-tag', 'tag-text', 'state-name', 'state-sub', 'result-card',
             'face-box', 'scan-line', 'btn-scan', 'check-in-hints'];

function kioskSandbox() {
  const els = {};
  for (const id of IDS) {
    els[id] = { className: '', textContent: '', innerHTML: '', disabled: null, style: { display: '' } };
  }
  const sb = {
    document: { getElementById: id => els[id] || null },
    setInterval: () => 1, clearInterval: () => {},
    Date, String, Number, Math, JSON, Set, console,
  };
  sb.window = sb;
  vm.createContext(sb);
  vm.runInContext(fs.readFileSync(path.join(__dirname, '..', 'ui', 'js', 'core', 'utils.js'), 'utf8'), sb);
  vm.runInContext(fs.readFileSync(path.join(__dirname, '..', 'ui', 'js', 'checkin', 'state-machine.js'), 'utf8'), sb);
  return { sb, els };
}

{
  const { sb, els } = kioskSandbox();

  sb.setState('idle');
  assert.strictEqual(sb.getCheckinState(), 'idle');
  assert.strictEqual(els['tag-text'].textContent, 'Waiting');
  assert.strictEqual(els['btn-scan'].disabled, false);
  assert.strictEqual(els['scan-line'].style.display, 'none');

  sb.setState('scanning');
  assert.strictEqual(els['btn-scan'].disabled, true, 'scanning must disable the button');
  assert.strictEqual(els['scan-line'].style.display, 'block');

  sb.setState('fail');
  assert.strictEqual(els['tag-text'].textContent, 'Unknown Face');
  assert.ok(els['result-card'].innerHTML.includes('Unknown Person'));

  sb.setState('confirmation', { name: 'Naimi Nafis', event: 'IN' });
  assert.strictEqual(sb.getCheckinState(), 'confirmation');
  assert.strictEqual(els['state-name'].innerHTML, 'Is This<br>Naimi Nafis?');
  assert.strictEqual(els['state-sub'].textContent, 'Will Check In');
  sb.setState('confirmation', { name: 'Naimi Nafis', event: 'OUT' });
  assert.strictEqual(els['state-sub'].textContent, 'Will Check Out');

  sb.setState('success', { name: 'Naimi Nafis', event: 'IN' });
  assert.strictEqual(sb.getCheckinState(), 'success');
  assert.strictEqual(els['state-name'].innerHTML, 'Welcome,<br>Naimi Nafis!');
  assert.ok(els['result-card'].innerHTML.includes('av-green'));
  assert.ok(els['result-card'].innerHTML.includes('>NN<'), 'avatar shows initials');
  sb.setState('success', { name: 'Naimi Nafis', event: 'OUT' });
  assert.strictEqual(els['state-name'].innerHTML, 'See You,<br>Naimi Nafis!');
  assert.ok(els['result-card'].innerHTML.includes('av-red'));

  // A member name is admin-supplied and lands in innerHTML.
  sb.setState('success', { name: '<img src=x onerror=alert(1)>', event: 'IN' });
  assert.ok(!els['state-name'].innerHTML.includes('<img'), 'name must be escaped');
  assert.ok(!els['result-card'].innerHTML.includes('<img'), 'name must be escaped in the card');

  // An unknown key is ignored rather than blanking the screen.
  const before = els['state-name'].innerHTML;
  sb.setState('no-such-state');
  assert.strictEqual(els['state-name'].innerHTML, before);
}

console.log('ui/js/checkin/state-machine.js: all assertions passed');
