// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.unittest.test_case');

base.unittest.testSuite('base.unittest.test_case_test', function() {
  test('parseFullyQualifiedName', function() {
    var p = base.unittest.TestCase.parseFullyQualifiedName('foo.bar');
    assertEquals(p.suiteName, 'foo');
    assertEquals(p.testCaseName, 'bar');
  });
});
