# Save menu in the plot window

## Problem

The "Plot along the wall" window shows the plot of a wall or an interface. Its footer had
four buttons next to **Close**: **Save PNG**, **Save PDF**, **Save SVG** and **Save CSV**.
They made the footer long and repeated the same word four times.

## Design

- The footer has one **Save ▾** button and **Close**.
- A click on **Save ▾** opens a small menu with **PNG**, **PDF**, **SVG** and **CSV**.
- A click on a format saves at once. It runs the same command as before,
  `results plot png|pdf|svg|csv`, so the window, the menu and the command box still agree.
- The save starts from the click on the menu item. The browser opens its save window only
  for a save that starts from a click, so this still works. (A `<select>` would start the
  save from a `change` event instead, and the browser does not always allow that.)
- The menu opens below the button. When there is no room below, it opens above the button.
- A second click on **Save ▾** closes the menu. A press outside the menu or Escape also
  closes it, as for every other menu. Closing the window closes the menu too.
- The button has `aria-haspopup="menu"` and `aria-expanded`.

## Implementation

- Only `frontend/js/patches.js` changes. `frontend/base/` stays frozen.
- The menu is drawn by the menus' own renderer, `App.Menu.build`, and is shown with
  `App.UI.popup`, so it looks and closes like the other menus.
- The page closes an open menu on any press outside it, on the **Save ▾** button too. The
  button notes that its press closed the menu, so the click after that press does not open
  it again.

## Tests

- Browser suite (`frontend/tests/test-patches-results.js`): every format is offered, a pick
  runs its command and saves the file, the button toggles the menu with the mouse and with
  the keyboard, the menu opens upward near the bottom of the window, and closing the window
  closes the menu.
- End to end (`tests/e2e/test_pictures.py`): the plot window saves a PNG at 300 dpi and a
  PDF through **Save ▾**.

## Documentation

`docs/USAGE.md` describes **Save ▾** and its four formats.
