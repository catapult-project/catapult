// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview ZipImporter inflates zip compressed data and passes it along
 * to an actual importer.
 */
tvcm.requireRawScript('jszip.js');
tvcm.requireRawScript('jszip-load.js');
tvcm.requireRawScript('jszip-inflate.js');

tvcm.require('tracing.importer.importer');
tvcm.require('tracing.importer.gzip_importer');
tvcm.require('tracing.trace_model');

tvcm.exportTo('tracing.importer', function() {
  var Importer = tracing.importer.Importer;

  function ZipImporter(model, eventData) {
    if (eventData instanceof ArrayBuffer)
      eventData = new Uint8Array(eventData);
    this.model_ = model;
    this.eventData_ = eventData;
  }

  /**
   * @param {eventData} string Possibly zip compressed data.
   * @return {boolean} Whether eventData looks like zip compressed data.
   */
  ZipImporter.canImport = function(eventData) {
    var header;
    if (eventData instanceof ArrayBuffer)
      header = new Uint8Array(eventData.slice(0, 2));
    else if (typeof(eventData) === 'string' || eventData instanceof String)
      header = [eventData.charCodeAt(0), eventData.charCodeAt(1)];
    else
      return false;
    return header[0] === 'P'.charCodeAt(0) && header[1] === 'K'.charCodeAt(0);
  };

  ZipImporter.prototype = {
    __proto__: Importer.prototype,

    extractSubtraces: function() {
      var zip = new JSZip(this.eventData_);
      var subtraces = [];
      for (var idx in zip.files)
        subtraces.push(zip.files[idx].asText());
      return subtraces;
    }
  };

  tracing.TraceModel.registerImporter(ZipImporter);

  return {
    ZipImporter: ZipImporter
  };
});
