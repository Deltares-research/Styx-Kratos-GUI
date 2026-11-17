/* Number fields (App.UI.el with type 'number'): a point as the decimal sign on every
   computer, whatever its region settings. */

function numberField(attrs) {
  return App.UI.el('input', Object.assign({ type: 'number' }, attrs || {}));
}

function typeInto(input, text) {
  input.value = text;
  input.setSelectionRange(text.length, text.length);
  input.dispatchEvent(new Event('input', { bubbles: true }));
}

function press(input, key) {
  var event = new KeyboardEvent('keydown', { key: key, bubbles: true, cancelable: true });
  input.dispatchEvent(event);
  return event;
}

test('a number field is a text field, so it shows its value with a point', function () {
  var input = numberField({ step: '0.1', value: '0.15' });
  T.eq(input.type, 'text');
  T.eq(input.getAttribute('inputmode'), 'decimal');
  T.ok(input.hasAttribute('data-number'), 'marked as a number field');
  T.eq(input.value, '0.15');
  input.value = String(2.5);
  T.eq(input.value, '2.5');
});

test('other inputs keep the type they were given', function () {
  T.eq(App.UI.el('input', { type: 'checkbox' }).type, 'checkbox');
  T.eq(App.UI.el('input', { type: 'text' }).hasAttribute('data-number'), false);
});

test('a typed comma becomes a point, before the listener of the caller sees it', function () {
  var seen = null;
  var input = numberField({ oninput: function () { seen = input.value; } });
  typeInto(input, '0,15');
  T.eq(input.value, '0.15');
  T.eq(seen, '0.15');
});

test('characters that are no part of a number are dropped; signs and exponents stay', function () {
  var input = numberField();
  typeInto(input, '1a2 m');
  T.eq(input.value, '12');
  typeInto(input, '-1.5e-3');
  T.eq(input.value, '-1.5e-3');
});

test('the caret stays after what was typed when a character is dropped', function () {
  var input = numberField();
  document.body.appendChild(input);
  try {
    input.value = '1x5';
    input.setSelectionRange(2, 2);
    input.dispatchEvent(new Event('input', { bubbles: true }));
    T.eq(input.value, '15');
    T.eq(input.selectionStart, 1);
  } finally { input.remove(); }
});

test('the arrow keys step the value by the step, within min and max', function () {
  var changes = 0;
  var input = numberField({ step: '0.1', min: '0', max: '0.3', value: '0.2',
                            onchange: function () { changes++; } });
  T.ok(press(input, 'ArrowUp').defaultPrevented);
  T.eq(input.value, '0.3', 'no 0.30000000000000004');
  press(input, 'ArrowUp');
  T.eq(input.value, '0.3', 'held at max');
  press(input, 'ArrowDown'); press(input, 'ArrowDown'); press(input, 'ArrowDown');
  press(input, 'ArrowDown');
  T.eq(input.value, '0', 'held at min');
  T.eq(changes, 4, 'each step reports a change; a key held at a limit does not');
});

test('without a step the arrow keys step by one; other keys are left alone', function () {
  var input = numberField({ value: '' });
  press(input, 'ArrowDown');
  T.eq(input.value, '-1');
  T.eq(press(input, 'a').defaultPrevented, false);
});
