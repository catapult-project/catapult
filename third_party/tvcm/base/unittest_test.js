// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.unittest');
base.require('base.raf');

base.unittest.testSuite('base.unittest_test', function() {


  test('promise', function() {
    return new Promise(function(r) {
      r.resolve();
    });
  });

  test('async', function() {
    return new Promise(function(r) {
      base.requestAnimationFrame(function() {
        r.resolve();
      });
    });
  });

  /* To test failures remove comments
  test('fail', function() {
    assertEquals(true, false);
  });

  test('rejected-promise', function() {
    return new Promise(function(resolver){
      resolver.reject("Failure by rejection");
    });
  });

   test('promise-that-throws-after-resolver', function() {
    return new Promise(function(resolver){
      throw new Error('blah');
    });
  });

  */
});
