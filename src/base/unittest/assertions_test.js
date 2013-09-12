// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.unittest.assertions');
base.require('base.quad');
base.require('base.rect');

base.requireRawScript('../third_party/gl-matrix/src/gl-matrix/common.js');
base.requireRawScript('../third_party/gl-matrix/src/gl-matrix/vec2.js');
base.requireRawScript('../third_party/gl-matrix/src/gl-matrix/vec3.js');

base.unittest.testSuite('base.unittest.assertions', function() {
  setup(function() {
    global.rawAssertThrows = function(fn) {
      try {
        fn();
      } catch (e) {
        if (e instanceof base.unittest.TestError)
          return;
        throw new Error('Unexpected error from <' + fn + '>: ' + e);
      }
      throw new Error('Expected <' + fn + '> to throw');
    };

    global.rawAssertNotThrows = function(fn) {
      try {
        fn();
      } catch (e) {
        throw new Error('Expected <' + fn + '> to not throw: ' + e.message);
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

  test('assertFalse', function() {
    rawAssertThrows(function() {
      assertFalse(true);
    });
    rawAssertNotThrows(function() {
      assertFalse(false);
    });
  });

  test('assertUndefined', function() {
    rawAssertThrows(function() {
      assertUndefined('');
    });
    rawAssertNotThrows(function() {
      assertUndefined(undefined);
    });
  });

  test('assertNotUndefined', function() {
    rawAssertThrows(function() {
      assertNotUndefined(undefined);
    });
    rawAssertNotThrows(function() {
      assertNotUndefined('');
    });
  });

  test('assertNull', function() {
    rawAssertThrows(function() {
      assertNull('');
    });
    rawAssertNotThrows(function() {
      assertNull(null);
    });
  });

  test('assertNotNull', function() {
    rawAssertThrows(function() {
      assertNotNull(null);
    });
    rawAssertNotThrows(function() {
      assertNotNull('');
    });
  });

  test('assertEquals', function() {
    rawAssertThrows(function() {
      assertEquals(1, 2);
    });
    rawAssertNotThrows(function() {
      assertEquals(1, 1);
    });

    try {
      var f = {};
      f.foo = f;
      assertEquals(1, f);
      throw new base.unittest.TestError('Failed to throw');
    } catch (e) {
      assertNotEquals('Converting circular structure to JSON', e.message);
    }

    try {
      var f = {};
      f.foo = f;
      assertEquals(f, 1);
      throw new base.unittest.TestError('Failed to throw');
    } catch (e) {
      assertNotEquals('Converting circular structure to JSON', e.message);
    }
  });

  test('assertNotEquals', function() {
    rawAssertThrows(function() {
      assertNotEquals(1, 1);
    });
    rawAssertNotThrows(function() {
      assertNotEquals(1, 2);
    });
  });

  test('assertArrayEquals', function() {
    rawAssertThrows(function() {
      assertArrayEquals([2, 3], [2, 4]);
    });
    rawAssertThrows(function() {
      assertArrayEquals([1], [1, 2]);
    });
    rawAssertNotThrows(function() {
      assertArrayEquals(['a', 'b'], ['a', 'b']);
    });
  });

  test('assertArrayEqualsShallow', function() {
    rawAssertThrows(function() {
      assertArrayShallowEquals([2, 3], [2, 4]);
    });
    rawAssertThrows(function() {
      assertArrayShallowEquals([1], [1, 2]);
    });
    rawAssertNotThrows(function() {
      assertArrayShallowEquals(['a', 'b'], ['a', 'b']);
    });
  });

  test('assertAlmostEquals', function() {
    rawAssertThrows(function() {
      assertAlmostEquals(1, 0);
    });
    rawAssertThrows(function() {
      assertAlmostEquals(1, 1.000011);
    });

    rawAssertNotThrows(function() {
      assertAlmostEquals(1, 1);
    });
    rawAssertNotThrows(function() {
      assertAlmostEquals(1, 1.000001);
    });
    rawAssertNotThrows(function() {
      assertAlmostEquals(1, 1 - 0.000001);
    });
  });

  test('assertVec2Equals', function() {
    rawAssertThrows(function() {
      assertVec2Equals(vec2.fromValues(0, 1), vec2.fromValues(0, 2));
    });
    rawAssertThrows(function() {
      assertVec2Equals(vec2.fromValues(1, 2), vec2.fromValues(2, 2));
    });
    rawAssertNotThrows(function() {
      assertVec2Equals(vec2.fromValues(1, 1), vec2.fromValues(1, 1));
    });
  });

  test('assertVec3Equals', function() {
    rawAssertThrows(function() {
      assertVec3Equals(vec3.fromValues(0, 1, 2), vec3.fromValues(0, 1, 3));
    });
    rawAssertThrows(function() {
      assertVec3Equals(vec3.fromValues(0, 1, 2), vec3.fromValues(0, 3, 2));
    });
    rawAssertThrows(function() {
      assertVec3Equals(vec3.fromValues(0, 1, 2), vec3.fromValues(3, 1, 2));
    });
    rawAssertNotThrows(function() {
      assertVec3Equals(vec3.fromValues(1, 2, 3), vec3.fromValues(1, 2, 3));
    });
  });

  test('assertQuadEquals', function() {
    rawAssertThrows(function() {
      assertQuadEquals(
          base.Quad.fromXYWH(1, 1, 2, 2), base.Quad.fromXYWH(1, 1, 2, 3));
    });
    rawAssertNotThrows(function() {
      assertQuadEquals(
          base.Quad.fromXYWH(1, 1, 2, 2), base.Quad.fromXYWH(1, 1, 2, 2));
    });
  });

  test('assertRectEquals', function() {
    rawAssertThrows(function() {
      assertRectEquals(
          base.Rect.fromXYWH(1, 1, 2, 2), base.Rect.fromXYWH(1, 1, 2, 3));
    });
    rawAssertNotThrows(function() {
      assertRectEquals(
          base.Rect.fromXYWH(1, 1, 2, 2), base.Rect.fromXYWH(1, 1, 2, 2));
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

  test('assertDoesNotThrow', function() {
    rawAssertThrows(function() {
      assertDoesNotThrow(function() {
        throw new Error('expected_error');
      });
    });
    rawAssertNotThrows(function() {
      assertDoesNotThrow(function() {
      });
    });
  });

  test('assertApproxEquals', function() {
    rawAssertThrows(function() {
      assertApproxEquals(1, 5, 0.5);
    });
    rawAssertNotThrows(function() {
      assertApproxEquals(1, 2, 1);
    });
  });

  test('assertVisible', function() {
    rawAssertThrows(function() {
      assertVisible({});
    });
    rawAssertThrows(function() {
      assertVisible({offsetHeight: 0});
    });
    rawAssertThrows(function() {
      assertVisible({offsetWidth: 0});
    });
    rawAssertNotThrows(function() {
      assertVisible({offsetWidth: 1, offsetHeight: 1});
    });
  });
});
