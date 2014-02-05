// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.guid');
base.require('base.unittest.constants');

base.exportTo('base.unittest', function() {
  var TestTypes = base.unittest.TestTypes;

  function TestCase(suite, testType, name, test, options) {
    this.guid_ = base.GUID.allocate();
    this.suite_ = suite;
    this.testType_ = testType;
    this.name_ = name;

    this.options_ = options;

    this.test_ = test;
  }

  TestCase.prototype = {
    __proto__: Object.prototype,

    get guid() {
      return this.guid;
    },

    get suite() {
      return this.suite_;
    },

    get testType() {
      return this.testType_;
    },

    get name() {
      return this.name_;
    },

    get fullyQualifiedName() {
      return this.suite_.name + '.' + this.name_;
    },

    get options() {
      return this.options_;
    },

    run: function(htmlHook) {
      return this.test_();
    },

    // TODO(nduca): The routing of this is a bit awkward. Probably better
    // to install a global function.
    addHTMLOutput: function(element) {
      base.unittest.addHTMLOutputForCurrentTest(element);
    }
  };

  function PerfTestCase(suite, name, test, options) {
    TestCase.call(this, suite, TestTypes.PERFTEST, name, test, options);
  }

  PerfTestCase.prototype = {
    __proto__: TestCase.prototype
  };

  return {
    TestCase: TestCase,
    PerfTestCase: PerfTestCase
  };
});
