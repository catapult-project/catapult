// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview A test harness loosely based on Python unittest, but that
 * installs global assert methods during the test for backward compatibility
 * with Closure tests.
 */
base.requireStylesheet('unittest');
base.exportTo('unittest', function() {

  function createTestCaseDiv(testName, opt_href, opt_alwaysShowErrorLink) {
    var el = document.createElement('test-case');

    var titleBlockEl = document.createElement('title');
    titleBlockEl.style.display = 'inline';
    el.appendChild(titleBlockEl);

    var titleEl = document.createElement('span');
    titleEl.style.marginRight = '20px';
    titleBlockEl.appendChild(titleEl);

    var errorLink = document.createElement('a');
    errorLink.textContent = 'Run individually...';
    if (opt_href)
      errorLink.href = opt_href;
    else
      errorLink.href = '#' + testName;
    errorLink.style.display = 'none';
    titleBlockEl.appendChild(errorLink);

    el.__defineSetter__('status', function(status) {
      titleEl.textContent = testName + ': ' + status;
      updateClassListGivenStatus(titleEl, status);
      if (status == 'FAILED' || opt_alwaysShowErrorLink)
        errorLink.style.display = '';
      else
        errorLink.style.display = 'none';
    });

    el.addError = function(test, e) {
      var errorEl = createErrorDiv(test, e);
      el.appendChild(errorEl);
      return errorEl;
    };

    el.addHTMLOutput = function(opt_title, opt_element) {
      var outputEl = createOutputDiv(opt_title, opt_element);
      el.appendChild(outputEl);
      return outputEl.contents;
    };

    el.status = 'READY';
    return el;
  }

  function createErrorDiv(test, e) {
    var el = document.createElement('test-case-error');
    el.className = 'unittest-error';

    var stackEl = document.createElement('test-case-stack');
    if (typeof e == 'string') {
      stackEl.textContent = e;
    } else if (e.stack) {
      var i = document.location.pathname.lastIndexOf('/');
      var path = document.location.origin +
          document.location.pathname.substring(0, i);
      var pathEscaped = path.replace(/[-/\\^$*+?.()|[\]{}]/g, '\\$&');
      var cleanStack = e.stack.replace(new RegExp(pathEscaped, 'g'), '.');
      stackEl.textContent = cleanStack;
    } else {
      stackEl.textContent = e;
    }
    el.appendChild(stackEl);
    return el;
  }

  function createOutputDiv(opt_title, opt_element) {
    var el = document.createElement('test-case-output');
    if (opt_title) {
      var titleEl = document.createElement('div');
      titleEl.textContent = opt_title;
      el.appendChild(titleEl);
    }
    var contentEl = opt_element || document.createElement('div');
    contentEl.style.border = '1px  solid black';
    el.appendChild(contentEl);

    el.__defineGetter__('contents', function() {
      return contentEl;
    });
    return el;
  }

  function statusToClassName(status) {
    if (status == 'PASSED')
      return 'unittest-green';
    else if (status == 'RUNNING' || status == 'READY')
      return 'unittest-yellow';
    else
      return 'unittest-red';
  }

  function updateClassListGivenStatus(el, status) {
    var newClass = statusToClassName(status);
    if (newClass != 'unittest-green')
      el.classList.remove('unittest-green');
    if (newClass != 'unittest-yellow')
      el.classList.remove('unittest-yellow');
    if (newClass != 'unittest-red')
      el.classList.remove('unittest-red');

    el.classList.add(newClass);
  }

  function HTMLTestRunner(opt_title, opt_curHash) {
    // This constructs a HTMLDivElement and then adds our own runner methods to
    // it. This is usually done via ui.js' define system, but we dont want our
    // test runner to be dependent on the UI lib. :)
    var outputEl = document.createElement('unittest-test-runner');
    outputEl.__proto__ = HTMLTestRunner.prototype;
    this.decorate.call(outputEl, opt_title, opt_curHash);
    return outputEl;
  }

  HTMLTestRunner.prototype = {
    __proto__: HTMLDivElement.prototype,

    decorate: function(opt_title, opt_curHash) {
      this.running = false;

      this.currentTest_ = undefined;
      this.results = undefined;
      if (opt_curHash) {
        var trimmedHash = opt_curHash.substring(1);
        this.filterFunc_ = function(testName) {
          return testName.indexOf(trimmedHash) == 0;
        };
      } else
        this.filterFunc_ = function(testName) { return true; };

      this.statusEl_ = document.createElement('title');
      this.appendChild(this.statusEl_);

      this.resultsEl_ = document.createElement('div');
      this.appendChild(this.resultsEl_);

      this.title_ = opt_title || document.title;

      this.updateStatus();
    },

    computeResultStats: function() {
      var numTestsRun = 0;
      var numTestsPassed = 0;
      var numTestsWithErrors = 0;
      if (this.results) {
        for (var i = 0; i < this.results.length; i++) {
          numTestsRun++;
          if (this.results[i].errors.length)
            numTestsWithErrors++;
          else
            numTestsPassed++;
        }
      }
      return {
        numTestsRun: numTestsRun,
        numTestsPassed: numTestsPassed,
        numTestsWithErrors: numTestsWithErrors
      };
    },

    updateStatus: function() {
      var stats = this.computeResultStats();
      var status;
      if (!this.results) {
        status = 'READY';
      } else if (this.running) {
        status = 'RUNNING';
      } else {
        if (stats.numTestsRun && stats.numTestsWithErrors == 0)
          status = 'PASSED';
        else
          status = 'FAILED';
      }

      updateClassListGivenStatus(this.statusEl_, status);
      this.statusEl_.textContent = this.title_ + ' [' + status + ']';
    },

    get done() {
      return this.results && this.running == false;
    },

    run: function(tests) {
      this.results = [];
      this.running = true;
      this.updateStatus();
      for (var i = 0; i < tests.length; i++) {
        if (!this.filterFunc_(tests[i].testName))
          continue;
        tests[i].run(this);
        this.updateStatus();
      }
      this.running = false;
      this.updateStatus();
    },

    willRunTest: function(test) {
      this.currentTest_ = test;
      this.currentResults_ = {testName: test.testName,
        errors: []};
      this.results.push(this.currentResults_);

      this.currentTestCaseEl_ = createTestCaseDiv(test.testName);
      this.currentTestCaseEl_.status = 'RUNNING';
      this.resultsEl_.appendChild(this.currentTestCaseEl_);
    },

    /**
     * Adds some html content to the currently running test
     * @param {String} opt_title The title for the output.
     * @param {HTMLElement} opt_element The element to add. If not added, then.
     * @return {HTMLElement} The element added, or if !opt_element, the element
     * created.
     */
    addHTMLOutput: function(opt_title, opt_element) {
      return this.currentTestCaseEl_.addHTMLOutput(opt_title, opt_element);
    },

    addError: function(e) {
      this.currentResults_.errors.push(e);
      return this.currentTestCaseEl_.addError(this.currentTest_, e);
    },

    didRunTest: function(test) {
      if (!this.currentResults_.errors.length)
        this.currentTestCaseEl_.status = 'PASSED';
      else
        this.currentTestCaseEl_.status = 'FAILED';

      this.currentResults_ = undefined;
      this.currentTest_ = undefined;
    }
  };

  function TestError(opt_message) {
    var that = new Error(opt_message);
    Error.captureStackTrace(that, TestError);
    that.__proto__ = TestError.prototype;
    return that;
  }

  TestError.prototype = {
    __proto__: Error.prototype
  };

  /*
   * @constructor TestCase
   */
  function TestCase(testMethod, opt_testMethodName) {
    if (!testMethod)
      throw new Error('testMethod must be provided');
    if (testMethod.name == '' && !opt_testMethodName)
      throw new Error('testMethod must have a name, ' +
                      'or opt_testMethodName must be provided.');

    this.testMethod_ = testMethod;
    this.testMethodName_ = opt_testMethodName || testMethod.name;
    this.results_ = undefined;
  };

  function forAllAssertAndEnsureMethodsIn_(prototype, fn) {
    for (var fieldName in prototype) {
      if (fieldName.indexOf('assert') != 0 &&
          fieldName.indexOf('ensure') != 0)
        continue;
      var fieldValue = prototype[fieldName];
      if (typeof fieldValue != 'function')
        continue;
      fn(fieldName, fieldValue);
    }
  }

  TestCase.prototype = {
    __proto__: Object.prototype,

    get testName() {
      return this.testMethodName_;
    },

    bindGlobals_: function() {
      forAllAssertAndEnsureMethodsIn_(TestCase.prototype,
          function(fieldName, fieldValue) {
            global[fieldName] = fieldValue.bind(this);
          });
    },

    unbindGlobals_: function() {
      forAllAssertAndEnsureMethodsIn_(TestCase.prototype,
          function(fieldName, fieldValue) {
            delete global[fieldName];
          });
    },

    /**
     * Adds some html content to the currently running test
     * @param {String} opt_title The title for the output.
     * @param {HTMLElement} opt_element The element to add. If not added, then.
     * @return {HTMLElement} The element added, or if !opt_element, the element
     * created.
     */
    addHTMLOutput: function(opt_title, opt_element) {
      return this.results_.addHTMLOutput(opt_title, opt_element);
    },

    assertTrue: function(a, opt_message) {
      if (a)
        return;
      var message = opt_message || 'Expected true, got ' + a;
      throw new TestError(message);
    },

    assertFalse: function(a, opt_message) {
      if (!a)
        return;
      var message = opt_message || 'Expected false, got ' + a;
      throw new TestError(message);
    },

    assertUndefined: function(a, opt_message) {
      if (a === undefined)
        return;
      var message = opt_message || 'Expected undefined, got ' + a;
      throw new TestError(message);
    },

    assertNotUndefined: function(a, opt_message) {
      if (a !== undefined)
        return;
      var message = opt_message || 'Expected not undefined, got ' + a;
      throw new TestError(message);
    },

    assertNull: function(a, opt_message) {
      if (a === null)
        return;
      var message = opt_message || 'Expected null, got ' + a;
      throw new TestError(message);
    },

    assertNotNull: function(a, opt_message) {
      if (a !== null)
        return;
      var message = opt_message || 'Expected non-null, got ' + a;
      throw new TestError(message);
    },

    assertEquals: function(a, b, opt_message) {
      if (a == b)
        return;
      var message = opt_message || 'Expected ' + a + ', got ' + b;
      throw new TestError(message);
    },

    assertNotEquals: function(a, b, opt_message) {
      if (a != b)
        return;
      var message = opt_message || 'Expected something not equal to ' + b;
      throw new TestError(message);
    },

    assertArrayEquals: function(a, b, opt_message) {
      if (a.length == b.length) {
        var ok = true;
        for (var i = 0; i < a.length; i++) {
          ok &= a[i] === b[i];
        }
        if (ok)
          return;
      }

      var message = opt_message || 'Expected array ' + a + ', got array ' + b;
      throw new TestError(message);
    },

    assertArrayShallowEquals: function(a, b, opt_message) {
      if (a.length == b.length) {
        var ok = true;
        for (var i = 0; i < a.length; i++) {
          ok &= a[i] === b[i];
        }
        if (ok)
          return;
      }

      var message = opt_message || 'Expected array ' + b + ', got array ' + a;
      throw new TestError(message);
    },

    assertAlmostEquals: function(a, b, opt_message) {
      if (Math.abs(a - b) < 0.00001)
        return;
      var message = opt_message || 'Expected almost ' + a + ', got ' + b;
      throw new TestError(message);
    },

    assertThrows: function(fn, opt_message) {
      try {
        fn();
      } catch (e) {
        return;
      }
      var message = opt_message || 'Expected throw from ' + fn;
      throw new TestError(message);
    },

    setUp: function() {
    },

    run: function(results) {
      this.bindGlobals_();
      try {
        this.results_ = results;
        results.willRunTest(this);

        // Set up.
        try {
          this.setUp();
        } catch (e) {
          results.addError(e);
          return;
        }

        // Run.
        try {
          this.testMethod_();
        } catch (e) {
          results.addError(e);
        }

        // Tear down.
        try {
          this.tearDown();
        } catch (e) {
          if (typeof e == 'string')
            e = new TestError(e);
          results.addError(e);
        }
      } finally {
        this.unbindGlobals_();
        results.didRunTest(this);
        this.results_ = undefined;
      }
    },

    tearDown: function() {
    }

  };

  /**
   * Returns an array of TestCase objects correpsonding to the tests
   * found in the given object. This considers any functions beginning with test
   * as a potential test.
   *
   * @param {object} opt_objectToEnumerate The object to enumerate, or global if
   * not specified.
   * @param {RegExp} opt_filter Return only tests that match this regexp.
   */
  function discoverTests(opt_objectToEnumerate, opt_filter) {
    var objectToEnumerate = opt_objectToEnumerate || global;

    var tests = [];
    for (var testMethodName in objectToEnumerate) {
      if (testMethodName.search(/^test.+/) != 0)
        continue;

      if (opt_filter && testMethodName.search(opt_filter) == -1)
        continue;

      var testMethod = objectToEnumerate[testMethodName];
      if (typeof testMethod != 'function')
        continue;
      var testCase = new TestCase(testMethod, testMethodName);
      tests.push(testCase);
    }
    tests.sort(function(a, b) {
      return a.testName.localeCompare(b.testName);
    });
    return tests;
  }

  /**
   * Runs all unit tests.
   */
  function runAllTests(opt_objectToEnumerate) {
    var runner;
    function init() {
      if (runner)
        runner.parentElement.removeChild(runner);
      runner = new HTMLTestRunner(document.title, document.location.hash);
      // Stash the runner on global so that the global test runner
      // can get to it.
      global.G_testRunner = runner;
    }

    function append() {
      document.body.appendChild(runner);
    }

    function run() {
      var objectToEnumerate = opt_objectToEnumerate || global;
      var tests = discoverTests(objectToEnumerate);
      runner.run(tests);
    }

    global.addEventListener('hashchange', function() {
      init();
      append();
      run();
    });

    init();
    if (document.body)
      append();
    else
      document.addEventListener('DOMContentLoaded', append);
    global.addEventListener('load', run);
  }

  if (/_test.html$/.test(document.location.pathname))
    runAllTests();

  return {
    HTMLTestRunner: HTMLTestRunner,
    TestError: TestError,
    TestCase: TestCase,
    discoverTests: discoverTests,
    runAllTests: runAllTests,
    createErrorDiv_: createErrorDiv,
    createTestCaseDiv_: createTestCaseDiv
  };
});
