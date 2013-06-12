// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.exportTo('base.unittest', function() {
  function TestError(opt_message) {
    var that = new Error(opt_message);
    Error.captureStackTrace(that, TestError);
    that.__proto__ = TestError.prototype;
    return that;
  }

  TestError.prototype = {
    __proto__: Error.prototype
  };

  return {
    TestError: TestError
  };
});
