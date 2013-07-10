// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.analysis.analysis_results');
base.require('tracing.analysis.stub_analysis_table');
base.require('tracing.selection');

base.unittest.testSuite('tracing.analysis.analysis_results', function() {
  test('selectionChangingLink', function() {
    var r = tracing.analysis.AnalysisResults();
    var track = {};
    var linkEl = r.createSelectionChangingLink('hello', function() {
      var selection = new tracing.Selection();
      selection.addSlice(track, {});
      return selection;
    });
    var didRequestSelectionChange = false;
    linkEl.addEventListener('requestSelectionChange', function(e) {
      didRequestSelectionChange = true;
    });
    linkEl.click();
    assertTrue(didRequestSelectionChange);
  });

  test('displayValuesInSummaryRow', function() {
    var r = new tracing.analysis.AnalysisResults();
    var table = new tracing.analysis.StubAnalysisTable();
    var node;
    assertEquals(0, table.nodeCount);

    r.appendSummaryRow(table, 'false_value', false);
    assertEquals(1, table.nodeCount);
    node = table.lastNode;
    assertEquals('false_value', node.children[0].innerText);
    assertEquals('false', node.children[1].innerText);

    r.appendSummaryRow(table, 'true_value', true);
    assertEquals(1, table.nodeCount);
    node = table.lastNode;
    assertEquals('true_value', node.children[0].innerText);
    assertEquals('true', node.children[1].innerText);

    r.appendSummaryRow(table, 'string_value', 'a string');
    assertEquals(1, table.nodeCount);
    node = table.lastNode;
    assertEquals('string_value', node.children[0].innerText);
    assertEquals('"a string"', node.children[1].innerText);

    r.appendSummaryRow(table, 'number_value', 12345);
    assertEquals(1, table.nodeCount);
    node = table.lastNode;
    assertEquals('number_value', node.children[0].innerText);
    assertEquals('12345', node.children[1].innerText);

    r.appendSummaryRow(table, 'undefined', undefined);
    assertEquals(1, table.nodeCount);
    node = table.lastNode;
    assertEquals('undefined', node.children[0].innerText);
    assertEquals('', node.children[1].innerText);

    assertEquals(0, table.nodeCount);
  });
});
