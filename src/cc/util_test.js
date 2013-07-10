// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('cc.util');

base.unittest.testSuite('cc.util', function() {
  test('nameConvert', function() {
    assertEquals('_foo', cc.convertNameToJSConvention('_foo'));
    assertEquals('foo_', cc.convertNameToJSConvention('foo_'));
    assertEquals('foo', cc.convertNameToJSConvention('foo'));
    assertEquals('fooBar', cc.convertNameToJSConvention('foo_bar'));
    assertEquals('fooBarBaz', cc.convertNameToJSConvention('foo_bar_baz'));
  });

  test('objectConvertNested', function() {
    var object = {
      un_disturbed: true,
      args: {
        foo_bar: {
          a_field: 7
        }
      }
    };
    var expected = {
      un_disturbed: true,
      args: {
        fooBar: {
          aField: 7
        }
      }
    };
    cc.preInitializeObject(object);
    assertObjectEquals(expected, object);
  });

  test('arrayConvert', function() {
    var object = {
      un_disturbed: true,
      args: [
        {foo_bar: 7},
        {foo_bar: 8}
      ]
    };
    var expected = {
      un_disturbed: true,
      args: [
        {fooBar: 7},
        {fooBar: 8}
      ]
    };
    cc.preInitializeObject(object);
    assertObjectEquals(expected, object);
  });
});
