// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('tvcm.unittest.test_case');

tvcm.unittest.testSuite('tvcm.unittest.test_case_test', function() {
  test('parseFullyQualifiedName', function() {
    var p = tvcm.unittest.TestCase.parseFullyQualifiedName('foo.bar');
    assertEquals(p.suiteName, 'foo');
    assertEquals(p.testCaseName, 'bar');
  });
});
