// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview ZipImporter inflates zip compressed data and passes it along
 * to an actual importer.
 */
base.requireRawScript('../third_party/jszip/jszip.js');
base.requireRawScript('../third_party/jszip/jszip-load.js');
base.requireRawScript('../third_party/jszip/jszip-inflate.js');

base.require('tracing.importer.importer');
base.require('tracing.importer.gzip_importer');
base.require('tracing.trace_model');

base.exportTo('tracing.importer', function() {
  var Importer = tracing.importer.Importer;

  function ZipImporter(model, eventData) {
    this.model_ = model;
    this.eventData_ = eventData;
  }

  /**
   * @param {eventData} string Possibly zip compressed data.
   * @return {boolean} Whether eventData looks like zip compressed data.
   */
  ZipImporter.canImport = function(eventData) {
    if (typeof(eventData) !== 'string' && !(eventData instanceof String))
      return false;
    return eventData[0] === 'P' && eventData[1] === 'K';
  };

  ZipImporter.prototype = {
    __proto__: Importer.prototype,

    extractSubtrace: function() {
      var zip = new JSZip(
          tracing.importer.GzipImporter.unescapeData_(this.eventData_));

      // TODO(dsinclair): We're only extracting the first file for now. Do
      //    we want to pull all files out of the archive if multiple exist?
      for (var idx in zip.files)
        return zip.files[idx].asText();
    },
  };

  tracing.TraceModel.registerImporter(ZipImporter);

  return {
    ZipImporter: ZipImporter
  };
});

