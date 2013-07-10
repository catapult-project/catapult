// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.unittest.assertions');

base.unittest.testSuite('base.unittest.assertions', function() {
  setup(function() {
    global.rawAssertThrows = function(fn) {
      try {
        fn();
      } catch (e) {
        return;
      }
      throw new Error('Expected <' + fn + '> to throw');
    };

    global.rawAssertNotThrows = function(fn) {
      try {
        fn();
      } catch (e) {
        throw new Error('Expected <' + fn + '> to not throw');
      }
    };
  });

  teardown(function() {
    global.rawAssertThrows = undefined;
    global.rawAssertNotThrows = undefined;
  });

  test('assertTrue', function() {
    rawAssertThrows(function() {
      assertTrue(false);
    });
    rawAssertNotThrows(function() {
      assertTrue(true);
    });
  });

  test('assertObjectEquals', function() {
    rawAssertThrows(function() {
      assertObjectEquals({a: 1}, {a: 2});
    });
    rawAssertThrows(function() {
      assertObjectEquals({a: 1}, []);
    });
    rawAssertThrows(function() {
      assertObjectEquals({a: 1, b: {}}, {a: 1, c: {}, b: {}});
    });
    rawAssertNotThrows(function() {
      assertObjectEquals({}, {});
    });
    rawAssertNotThrows(function() {
      assertObjectEquals({a: 1}, {a: 1});
    });
  });

  test('assertThrows', function() {
    rawAssertThrows(function() {
      assertThrows(function() {
      });
    });
    rawAssertNotThrows(function() {
      assertThrows(function() {
        throw new Error('expected_error');
      });
    });
  });
});
