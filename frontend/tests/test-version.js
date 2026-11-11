/* test-version.js — the version the title bar and the About box show is the one
   the server wrote into the page, not the frozen js/data.js's own. */

(function () {
  function page(meta) {
    var doc = document.implementation.createHTMLDocument('');
    if (meta !== undefined) doc.head.innerHTML = meta;
    return doc;
  }

  test('the version is the one the server wrote into the page', function () {
    T.eq(App.Version.fromPage(page('<meta name="styx-version" content="0.1.0+12.g2408259">')),
         '0.1.0+12.g2408259');
  });

  test('a page the server did not fill says it does not know', function () {
    T.eq(App.Version.fromPage(page('<meta name="styx-version" content="">')),
         App.Version.UNKNOWN);
    T.eq(App.Version.fromPage(page()), App.Version.UNKNOWN);
  });

  test('the frozen prototype version is no longer shown', function () {
    T.ok(App.PRODUCT.version !== 'Prototype V1.0', App.PRODUCT.version);
  });
})();
