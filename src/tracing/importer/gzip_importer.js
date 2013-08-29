// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview GzipImporter inflates gzip compressed data and passes it along
 * to an actual importer.
 */
base.require('tracing.importer.importer');
base.require('tracing.trace_model');
base.requireRawScript('../third_party/jszip/jszip.js');
base.requireRawScript('../third_party/jszip/jszip-inflate.js');

base.exportTo('tracing.importer', function() {

  var Importer = tracing.importer.Importer;

  var GZIP_HEADER_ID1 = 0x1f;
  var GZIP_HEADER_ID2 = 0x8b;
  var GZIP_DEFLATE_COMPRESSION = 8;

  function GzipImporter(model, eventData) {
    this.model_ = model;
    this.gzipData_ = eventData;
  }

  /**
   * @param {eventData} Possibly gzip compressed data. Assumed to be escaped
   *                    as described in {unescapeData_} below.
   * @return {boolean} Whether obj looks like gzip compressed data.
   */
  GzipImporter.canImport = function(eventData) {
    if (typeof(eventData) !== 'string' && !(eventData instanceof String))
      return false;
    // To avoid unescaping the entire data set, construct the equivalent
    // escaped gzip header and check against it.
    var expected_header = this.escapeData_(
        String.fromCharCode(GZIP_HEADER_ID1) +
        String.fromCharCode(GZIP_HEADER_ID2) +
        String.fromCharCode(GZIP_DEFLATE_COMPRESSION));
    var actual_header = eventData.slice(0, expected_header.length);
    return actual_header === expected_header;
  };

  /**
   * @param {data} A string that has been escaped so that negative bytes
   *               (> 0x7f) are represented as a charcode of 0xffff followed
   *               by the byte value encoded as four hexadecimal characters.
   * @return {string} Unescaped string.
   */
  GzipImporter.unescapeData_ = function(data) {
    var result = [];
    for (var i = 0; i < data.length; i++) {
      var charCode = data.charCodeAt(i);
      if (charCode == 0xffff) {
        if (i + 4 >= data.length)
          throw new Error('Unexpected end of gzip data');
        charCode = parseInt(data.substr(i + 1, 4), 16) & 0xff;
        i += 4;
      }
      result.push(String.fromCharCode(charCode));
    }
    return result.join('');
  };

  /**
   * @return {string} The input string escaped as described in unescapeData_.
   */
  GzipImporter.escapeData_ = function(data) {
    var result = [];
    for (var i = 0; i < data.length; i++) {
      var charCode = data.charCodeAt(i);
      if (charCode > 0x7f)
        result.push(String.fromCharCode(-1) + 'ff' + charCode.toString(16));
      else
        result.push(String.fromCharCode(charCode));
    }
    return result.join('');
  };

  /**
   * Inflates (decompresses) the data stored in the given gzip bitstream.
   * @return {string} Inflated data.
   */
  GzipImporter.inflateGzipData_ = function(data) {
    var position = 0;

    function getByte() {
      if (position >= data.length)
        throw new Error('Unexpected end of gzip data');
      return data.charCodeAt(position++) & 0xff;
    }

    function getWord() {
      var low = getByte();
      var high = getByte();
      return (high << 8) + low;
    }

    function skipBytes(amount) {
      position += amount;
    }

    function skipZeroTerminatedString() {
      while (getByte() != 0) {}
    }

    var id1 = getByte();
    var id2 = getByte();
    if (id1 !== GZIP_HEADER_ID1 || id2 !== GZIP_HEADER_ID2)
      throw new Error('Not gzip data');
    var compression_method = getByte();
    if (compression_method !== GZIP_DEFLATE_COMPRESSION)
      throw new Error('Unsupported compression method: ' + compression_method);
    var flags = getByte();
    var have_header_crc = flags & (1 << 1);
    var have_extra_fields = flags & (1 << 2);
    var have_file_name = flags & (1 << 3);
    var have_comment = flags & (1 << 4);

    // Skip modification time, extra flags and OS.
    skipBytes(4 + 1 + 1);

    // Skip remaining fields before compressed data.
    if (have_extra_fields) {
      var bytes_to_skip = getWord();
      skipBytes(bytes_to_skip);
    }
    if (have_file_name)
      skipZeroTerminatedString();
    if (have_comment)
      skipZeroTerminatedString();
    if (have_header_crc)
      getWord();

    // Inflate the data using jszip.
    var buffer = JSZip.utils.transformTo('uint8array', data.substr(position));
    var inflated_data = JSZip.compressions['DEFLATE'].uncompress(buffer);
    return JSZip.utils.transformTo('string', inflated_data);
  },

  GzipImporter.prototype = {
    __proto__: Importer.prototype,

    /**
     * Called by the Model to extract a subtrace from the event data. The
     * subtrace is passed on to other importers that can recognize it.
     */
    extractSubtrace: function() {
      var data = GzipImporter.unescapeData_(this.gzipData_);
      return GzipImporter.inflateGzipData_(data);
    },
  };

  tracing.TraceModel.registerImporter(GzipImporter);

  return {
    GzipImporter: GzipImporter
  };
});
