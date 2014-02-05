// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.unittest.test_case');
base.require('base.unittest.constants');

base.exportTo('base.unittest', function() {
  var TestCase = base.unittest.TestCase;
  var PerfTestCase = base.unittest.PerfTestCase;

  var TestTypes = base.unittest.TestTypes;

  function TestSuite(loader, name, suiteConstructor) {
    this.loader_ = loader;
    this.name_ = name;
    this.tests_ = [];
    this.testNames_ = {}; // For dupe checking.

    global.test = function(name, test, options) {
      if (test == undefined)
        throw new Error('Must provide test');
      options = options || {};
      var testName = name;
      // If the test cares about DPI settings then we first push a test
      // that fakes the DPI as the low or hi Dpi version, depending on what
      // we're current using.
      if (options.dpiAware) {
        var defaultDevicePixelRatio = window.devicePixelRatio;
        var dpi = defaultDevicePixelRatio > 1 ? 1 : 2;

        var testWrapper = function() {
          window.devicePixelRatio = dpi;
          try {
            test.bind(this).call();
          } finally {
            window.devicePixelRatio = defaultDevicePixelRatio;
          }
        };

        var newName = name;
        if (dpi === 1) {
          newName += '_loDPI';
          testName += '_hiDPI';
        } else {
          newName += '_hiDPI';
          testName += '_loDPI';
        }

        this.addTest(new TestCase(this, TestTypes.UNITTEST, newName,
                                  testWrapper, options || {}));
      }

      this.addTest(new TestCase(this, TestTypes.UNITTEST, testName,
                                test, options || {}));
    }.bind(this);

    global.perfTest = function(name, test, options) {
      this.addTest(new PerfTestCase(this, name, test, options || {}));
    }.bind(this);

    global.timedPerfTest = function(name, test, options) {
      if (options === undefined || options.iterations === undefined)
        throw new Error('timedPerfTest must have iteration option provided.');

      var testWrapper = function(results) {
        results = [];
        for (var i = 0; i < options.iterations; ++i) {
          var start = window.performance.now();
          test.call(this);
          var duration = window.performance.now() - start;
          results.push(duration.toFixed(2) + 'ms');
        }
        return results.join(', ');
      };

      this.addTest(new PerfTestCase(this, name, testWrapper, options));
    }.bind(this);

    suiteConstructor.call();

    global.test = undefined;
    global.perfTest = undefined;
    global.timedPerfTest = undefined;
  }

  TestSuite.prototype = {
    __proto__: Object.prototype,

    get tests() {
      return this.tests_;
    },

    addTest: function(test) {
      if (this.testNames_[test.name] !== undefined)
        throw new Error('Test name already used');
      this.testNames_[test.name] = true;
      this.tests_.push(test);
    },

    get name() {
      return this.name_;
    }
  };

  return {
    TestSuite: TestSuite
  };
});
