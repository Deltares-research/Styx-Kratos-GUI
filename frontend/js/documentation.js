/* ══════════════════════════════════════════════════════════════════
   documentation.js — Help > Documentation (F1) and Help > GUI tutorials.

   Both open a page of the documentation site in a new browser tab. The site is
   built from the pages of the repository (tools/docs_site.py, mkdocs.yml) and
   published from main on GitHub Pages (.github/workflows/docs-site.yml). SITE is
   the `site_url` of mkdocs.yml, and each page is one of its nav; the Python test
   tests/test_docs_site.py holds the two together.

   The tab is opened with `noopener`, so the browser gives nothing back to tell
   whether a pop-up blocker stopped it. The log says the address either way, so
   the user can copy it.

   No DOM in it, so the headless runner executes it
   (frontend/tests/test-documentation.js).
   ══════════════════════════════════════════════════════════════════ */

(function (App) {
  'use strict';

  var SITE = 'https://ubiquitous-adventure-vo3qvvw.pages.github.io/';

  /* The pages the Help menu opens, as the site names them. */
  var PAGES = {
    home: 'index.html',
    tutorials: 'docs/gui_tutorials/index.html'
  };

  /* The address of a page of the site; the home page for a name it does not know. */
  function url(page) {
    return SITE + (PAGES[page] || PAGES.home);
  }

  /* Opens the page in a new tab and says where, in the log. Returns the address. */
  function open(page) {
    var address = url(page);
    if (typeof window.open === 'function') window.open(address, '_blank', 'noopener');
    if (App.Command && App.Command.note) {
      App.Command.note('Documentation: ' + address);
    }
    return address;
  }

  App.Documentation = { SITE: SITE, PAGES: PAGES, url: url, open: open };

})(window.App = window.App || {});
