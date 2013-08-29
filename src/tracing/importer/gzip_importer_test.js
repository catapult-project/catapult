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

  test('inflate', function() {
    // Test inflating the data directly.
    var gzip_data = atob(gzip_data_base64);
    self.assertEquals(original_data,
        tracing.importer.GzipImporter.inflateGzipData_(gzip_data));
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
