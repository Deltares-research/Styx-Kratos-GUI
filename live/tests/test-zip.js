/* zip.js — the one file a Kratos deck is saved as.

   Read back the way a zip reader reads it: the central directory at the end
   names the entries, and each one points at its own local header. Anything the
   assembly gets wrong shows up as a name or an offset that does not line up. */

function readZip(blob) {
  return blob.arrayBuffer().then(function (buffer) {
    var bytes = new Uint8Array(buffer), view = new DataView(buffer);
    var decoder = new TextDecoder();

    var end = bytes.length - 22;
    while (end >= 0 && view.getUint32(end, true) !== 0x06054B50) end--;
    T.ok(end >= 0, 'no end-of-central-directory record: not a zip at all');

    var count = view.getUint16(10 + end, true);
    var at = view.getUint32(16 + end, true);
    var entries = [];
    for (var i = 0; i < count; i++) {
      T.eq(view.getUint32(at, true), 0x02014B50, 'central directory entry ' + i);
      var nameLength = view.getUint16(at + 28, true);
      var name = decoder.decode(bytes.subarray(at + 46, at + 46 + nameLength));
      var size = view.getUint32(at + 24, true);
      var local = view.getUint32(at + 42, true);

      T.eq(view.getUint32(local, true), 0x04034B50, 'local header for ' + name);
      T.eq(view.getUint16(local + 8, true), 0, 'stored, so any reader can open it');
      var data = local + 30 + view.getUint16(local + 26, true)
                 + view.getUint16(local + 28, true);
      entries.push({ name: name, text: decoder.decode(bytes.subarray(data, data + size)) });
      at += 46 + nameLength + view.getUint16(at + 30, true) + view.getUint16(at + 32, true);
    }
    return entries;
  });
}

test('the archive holds every file, in order, byte for byte', function () {
  var blob = App.Zip.create([
    { name: 'model.mdpa', text: 'Begin Properties 0\r\nEnd Properties\r\n' },
    { name: 'MaterialParameters.json', text: '{"properties": []}' },
    { name: 'ProjectParameters.json', text: '{"solver_settings": {}}' }
  ]);
  T.eq(blob.type, 'application/zip');
  return readZip(blob).then(function (entries) {
    T.eq(entries.map(function (e) { return e.name; }),
         ['model.mdpa', 'MaterialParameters.json', 'ProjectParameters.json']);
    T.eq(entries[0].text, 'Begin Properties 0\r\nEnd Properties\r\n',
         'the deck\'s line endings are the ones Kratos is given');
    T.eq(entries[2].text, '{"solver_settings": {}}');
  });
});

test('non-ASCII survives the round trip', function () {
  return readZip(App.Zip.create([{ name: 'Rotterdam — Zuid.mdpa', text: 'σ = 12 kN/m²' }]))
    .then(function (entries) {
      T.eq(entries[0].name, 'Rotterdam — Zuid.mdpa');
      T.eq(entries[0].text, 'σ = 12 kN/m²');
    });
});

test('the checksum is the one every zip reader will compute', function () {
  // The published CRC-32 of "123456789"; a wrong table or a wrong final XOR
  // gives an archive that opens as corrupt.
  T.eq(App.Zip.crc32(new TextEncoder().encode('123456789')), 0xCBF43926);
  T.eq(App.Zip.crc32(new Uint8Array(0)), 0);
});

test('an empty archive is still a readable zip', function () {
  return readZip(App.Zip.create([])).then(function (entries) { T.eq(entries.length, 0); });
});
