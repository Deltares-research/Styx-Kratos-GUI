/* ══════════════════════════════════════════════════════════════════
   zip.js — the export, as one file.

   A Kratos deck is three files, and a browser can only be handed one save
   window per click: showSaveFilePicker is refused the moment an await has
   intervened, and the mesh takes minutes. A folder handle would take all three,
   but Chrome will not give one out without a separate "let this site edit
   files" grant, and it refuses whole trees — C:\, Program Files, Windows —
   outright. So the deck is zipped and saved as one file the user names.

   Stored, not deflated: an .mdpa is large but the archive is opened once,
   immediately, and DEFLATE would mean shipping a compressor. Every zip reader
   handles method 0.
   ══════════════════════════════════════════════════════════════════ */

var App = window.App || {};

App.Zip = (function () {

  var CRC_TABLE = (function () {
    var table = new Uint32Array(256), c, n, k;
    for (n = 0; n < 256; n++) {
      c = n;
      for (k = 0; k < 8; k++) c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1);
      table[n] = c >>> 0;
    }
    return table;
  })();

  function crc32(bytes) {
    var c = 0xFFFFFFFF;
    for (var i = 0; i < bytes.length; i++) {
      c = CRC_TABLE[(c ^ bytes[i]) & 0xFF] ^ (c >>> 8);
    }
    return (c ^ 0xFFFFFFFF) >>> 0;
  }

  /* MS-DOS date and time, which is what a zip records: two seconds of
     resolution and no year before 1980. */
  function stamp(when) {
    return {
      time: (when.getHours() << 11) | (when.getMinutes() << 5)
            | (Math.floor(when.getSeconds() / 2)),
      date: ((Math.max(when.getFullYear(), 1980) - 1980) << 9)
            | ((when.getMonth() + 1) << 5) | when.getDate()
    };
  }

  function block(size, fill) {
    var bytes = new Uint8Array(size);
    fill(new DataView(bytes.buffer));
    return bytes;
  }

  /* files: [{ name, text }] — text may be a string or already bytes. */
  function create(files, when) {
    var encoder = new TextEncoder();
    var at = stamp(when || new Date());
    var parts = [], directory = [], offset = 0, entries = 0, directorySize = 0;

    (files || []).forEach(function (file) {
      var name = encoder.encode(file.name);
      var data = typeof file.text === 'string' ? encoder.encode(file.text) : file.text;
      var crc = crc32(data);

      var local = block(30, function (v) {
        v.setUint32(0, 0x04034B50, true);
        v.setUint16(4, 20, true);
        v.setUint16(6, 0x0800, true);   // the names are UTF-8
        v.setUint16(8, 0, true);        // stored
        v.setUint16(10, at.time, true);
        v.setUint16(12, at.date, true);
        v.setUint32(14, crc, true);
        v.setUint32(18, data.length, true);
        v.setUint32(22, data.length, true);
        v.setUint16(26, name.length, true);
        v.setUint16(28, 0, true);
      });
      parts.push(local, name, data);

      directory.push(block(46, function (v) {
        v.setUint32(0, 0x02014B50, true);
        v.setUint16(4, 20, true);
        v.setUint16(6, 20, true);
        v.setUint16(8, 0x0800, true);
        v.setUint16(10, 0, true);
        v.setUint16(12, at.time, true);
        v.setUint16(14, at.date, true);
        v.setUint32(16, crc, true);
        v.setUint32(20, data.length, true);
        v.setUint32(24, data.length, true);
        v.setUint16(28, name.length, true);
        v.setUint32(42, offset, true);
      }), name);
      directorySize += 46 + name.length;
      offset += 30 + name.length + data.length;
      entries += 1;
    });

    var end = block(22, function (v) {
      v.setUint32(0, 0x06054B50, true);
      v.setUint16(8, entries, true);
      v.setUint16(10, entries, true);
      v.setUint32(12, directorySize, true);
      v.setUint32(16, offset, true);
    });

    return new Blob(parts.concat(directory, [end]), { type: 'application/zip' });
  }

  return { create: create, crc32: crc32 };
})();
