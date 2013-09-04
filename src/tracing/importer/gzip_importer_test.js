// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.test_utils');
base.require('tracing.importer.gzip_importer');
base.require('tracing.importer.trace_event_importer');

base.unittest.testSuite('tracing.importer.gzip_importer', function() {
  var findSliceNamed = tracing.test_utils.findSliceNamed;
  var original_data =
      '[{"name":"a","args":{},"pid":52,"ts":520,"cat":"foo","tid":53,' +
      '"ph":"B"},{"name":"a","args":{},"pid":52,"ts":520,"cat":"foo",' +
      '"tid":53,"ph":"E"}]\n';
  var gzip_data_base64 =
      'H4sICHr4HVIAA3RyYWNlAIuuVspLzE1VslJKVNJRSixKL1ayqq7VUSrITFGy' +
      'MjXSUSopBtEGOkrJiSVAVWn5+UB1JWBZY6CyDKCYk1KtDhWMcVWqjeUCALak' +
      'EH+QAAAA';

  test('failImportEmpty', function() {
    self.assertFalse(tracing.importer.GzipImporter.canImport([]));
    self.assertFalse(tracing.importer.GzipImporter.canImport(''));
  });

  test('inflateString', function() {
    // Test inflating the data from a string.
    var gzip_data = atob(gzip_data_base64);
    gzip_data = tracing.importer.GzipImporter.escapeData_(gzip_data);
    var importer = new tracing.importer.GzipImporter(null, gzip_data);
    self.assertTrue(tracing.importer.GzipImporter.canImport(gzip_data));
    self.assertEquals(original_data, importer.extractSubtraces()[0]);
  });

  test('inflateArrayBuffer', function() {
    // Test inflating the data from an ArrayBuffer.
    var gzip_data = atob(gzip_data_base64);
    var buffer = new ArrayBuffer(gzip_data.length);
    var view = new Uint8Array(buffer);
    for (var i = 0; i < gzip_data.length; i++)
      view[i] = gzip_data.charCodeAt(i);
    var importer = new tracing.importer.GzipImporter(null, buffer);
    self.assertTrue(tracing.importer.GzipImporter.canImport(buffer));
    self.assertEquals(original_data, importer.extractSubtraces()[0]);
  });

  test('import', function() {
    // Load the escaped version of the data into a Model.
    var gzip_data = atob(gzip_data_base64);
    gzip_data = tracing.importer.GzipImporter.escapeData_(gzip_data);
    self.assertTrue(tracing.importer.GzipImporter.canImport(gzip_data));

    var model = new tracing.TraceModel(gzip_data);
    var threads = model.getAllThreads();
    self.assertEquals(threads.length, 1);

    var slice = findSliceNamed(threads[0].sliceGroup, 'a');
    self.assertEquals(slice.category, 'foo');
  });
});
