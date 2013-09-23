// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('ui.trace_viewer');
base.requireStylesheet('base.unittest');

base.require('base.key_event_manager');
base.require('base.promise');
base.require('base.settings');
base.require('base.unittest.test_error');
base.require('base.unittest.assertions');

base.exportTo('base.unittest', function() {
  var TestStatus = {
    FAILED: 0,
    PASSED: 1,
    PENDING: 2
  };

  var TestTypes = {
    UNITTEST: 0,
    PERFTEST: 1
  };

  var showCondensed_ = false;
  var testType_ = TestTypes.UNITTEST;

  function showCondensed(val) {
    showCondensed_ = val;
  }

  function testType(val) {
    if (val === 'perf')
      testType_ = TestTypes.PERFTEST;
    else
      testType_ = TestTypes.UNITTEST;
  }

  function logWarningMessage(message) {
    var messagesEl = document.querySelector('#messages');
    messagesEl.setAttribute('hasMessages', true);

    var li = document.createElement('li');
    li.innerText = message;

    var list = document.querySelector('#message-list');
    list.appendChild(li);
  }

  function TestRunner(tests) {
    this.suites_ = [];
    this.suiteNames_ = {};
    this.tests_ = tests || [];
    this.moduleCount_ = 0;

    this.stats_ = {
      tests: 0,
      failures: 0,
      exceptions: [],
      duration: 0.0
    };
  }

  TestRunner.prototype = {
    __proto__: Object.prototype,

    run: function() {
      this.clear_(document.querySelector('#test-results'));
      this.clear_(document.querySelector('#exception-list'));

      this.updateStats_();
      this.runSuites_();
    },

    addSuite: function(suite) {
      if (this.suiteNames_[suite.name] === true)
        logWarningMessage('Duplicate test suite name detected: ' + suite.name);

      this.suites_.push(suite);
      this.suiteNames_[suite.name] = true;
    },

    get suiteCount() {
      return this.suites_.length;
    },

    clear_: function(el) {
      while (el.firstChild)
        el.removeChild(el.firstChild);
    },

    runSuites_: function(opt_idx) {
      var idx = opt_idx || 0;

      var suiteCount = this.suites_.length;
      if (idx >= suiteCount) {
        var harness = document.querySelector('#test-results');
        harness.appendChild(document.createElement('br'));
        harness.appendChild(document.createTextNode('Test Run Complete'));
        return;
      }

      var suite = this.suites_[idx];
      suite.showLongResults = (suiteCount === 1);
      suite.displayInfo();
      return suite.runTests(this.tests_).then(function(ignored) {
        this.stats_.duration += suite.duration;
        this.stats_.tests += suite.testCount;
        this.stats_.failures += suite.failureCount;

        this.updateStats_();
        return this.runSuites_(idx + 1);
      }.bind(this));
    },

    onAnimationFrameError: function(e, opt_stack) {
      if (e.message)
        console.error(e.message, e.stack);
      else
        console.error(e);

      var exception = {e: e, stack: opt_stack};
      this.stats_.exceptions.push(exception);
      this.appendException(exception);
      this.updateStats_();
    },

    updateStats_: function() {
      var statEl = document.querySelector('#stats');
      statEl.innerHTML =
          this.suites_.length + ' suites, ' +
          '<span class="passed">' + this.stats_.tests + '</span> tests, ' +
          '<span class="failed">' + this.stats_.failures +
          '</span> failures, ' +
          '<span class="exception">' + this.stats_.exceptions.length +
          '</span> exceptions,' +
          ' in ' + this.stats_.duration.toFixed(2) + 'ms.';
    },

    appendException: function(exc) {
      var exceptionsEl = document.querySelector('#exceptions');
      exceptionsEl.setAttribute('hasExceptions', this.stats_.exceptions.length);

      var excEl = document.createElement('li');
      excEl.innerHTML = exc.e + '<pre>' + exc.stack + '</pre>';

      var exceptionsEl = document.querySelector('#exception-list');
      exceptionsEl.appendChild(excEl);
    }
  };

  function TestSuite(name, suite) {
    this.name_ = name;
    this.tests_ = [];
    this.testNames_ = {};
    this.failures_ = [];
    this.showLongResults = false;
    this.duration_ = 0.0;
    this.resultsEl_ = undefined;

    global.setupOnce = function(fn) { this.setupOnceFn_ = fn; }.bind(this);
    global.setup = function(fn) { this.setupFn_ = fn; }.bind(this);
    global.teardown = function(fn) { this.teardownFn_ = fn; }.bind(this);

    global.test = function(name, test, options) {
      options = options || {};

      if (this.testNames_[name] === true)
        logWarningMessage('Duplicate test name detected: ' + name);

      var testName = name;
      // If the test cares about DPI settings then we first push a test
      // that fakes the DPI as the low or hi Dpi version, depending on what
      // we're current using.
      if (options.dpiAware) {
        var defaultDevicePixelRatio = window.devicePixelRatio;
        var dpi = defaultDevicePixelRatio > 1 ? 1 : 2;

        var testWrapper = function() {
          window.devicePixelRatio = dpi;
          test.bind(this).call();
          window.devicePixelRatio = defaultDevicePixelRatio;
        };

        var newName = name;
        if (dpi === 1) {
          newName += '_loDPI';
          testName += '_hiDPI';
        } else {
          newName += '_hiDPI';
          testName += '_loDPI';
        }

        this.tests_.push(new Test(newName, testWrapper, options || {}));
      }

      this.tests_.push(new Test(testName, test, options || {}));
      this.testNames_[name] = true;
    }.bind(this);

    global.perfTest = function(name, test, options) {
      if (this.testNames_[name] === true)
        logWarningMessage('Duplicate test name detected: ' + name);

      this.tests_.push(new PerfTest(name, test, options || {}));
      this.testNames_[name] = true;
    }.bind(this);

    global.timedPerfTest = function(name, test, options) {
      if (options === undefined || options.iterations === undefined)
        throw new Error('timedPerfTest must have iteration option provided.');

      name += '_' + options.iterations;
      if (this.testNames_[name] === true)
        logWarningMessage('Duplicate test name detected: ' + name);

      options.results = options.results || TimingTestResult;
      var testWrapper = function(results) {
        results.testCount = options.iterations;
        for (var i = 0; i < options.iterations; ++i) {
          var start = window.performance.now();
          test.bind(this).call();
          results.add(window.performance.now() - start);
        }
      };

      this.tests_.push(new PerfTest(name, testWrapper, options));
      this.testNames_[name] = true;
    }.bind(this);

    suite.call();

    global.setupOnce = undefined;
    global.setup = undefined;
    global.teardown = undefined;
    global.test = undefined;
    global.perfTest = undefined;
    global.timedPerfTest = undefined;
  }

  TestSuite.prototype = {
    __proto__: Object.prototype,

    get name() {
      return this.name_;
    },

    get results() {
      return (this.failureCount > 0) ? TestStatus.FAILED : TestStatus.PASSED;
    },

    get testCount() {
      return this.tests_.length;
    },

    get failureCount() {
      return this.failures.length;
    },

    get failures() {
      return this.failures_;
    },

    get duration() {
      return this.duration_;
    },

    displayInfo: function() {
      this.resultsEl_ = document.createElement('div');
      this.resultsEl_.className = 'test-result';

      var resultsPanel = document.querySelector('#test-results');
      resultsPanel.appendChild(this.resultsEl_);

      if (this.showLongResults) {
        this.resultsEl_.innerText = this.name;
      } else {
        var link = '/src/tests.html?suite=';
        link += this.name.replace(/\./g, '/');
        link += '&type=' + (testType_ === TestTypes.PERFTEST ? 'perf' : 'unit');

        var suiteInfo = document.createElement('a');
        suiteInfo.href = link;
        suiteInfo.innerText = this.name;
        this.resultsEl_.appendChild(suiteInfo);
      }

      var statusEl = document.createElement('span');
      statusEl.classList.add('results');
      statusEl.classList.add('pending');
      statusEl.innerText = 'pending';
      this.resultsEl_.appendChild(statusEl);
    },

    runTests: function(testsToRun) {
      this.testsToRun_ = testsToRun;

      if (this.setupOnceFn_ !== undefined)
        this.setupOnceFn_.bind(this).call();

      var remainingTests;
      if (testsToRun.length) {
        remainingTests = this.tests_.reduce(function(remainingTests, test) {
          if (this.testsToRun_.indexOf(test.name) !== -1)
            remainingTests.push(test);
          return remainingTests;
        }.bind(this), []);
      } else {
        remainingTests = this.tests_.slice(0);
      }

      return this.runRemainingTests_(remainingTests).then(
          function resolve(ignored) {
            this.duration_ = this.tests_.reduce(function(total, test) {
              return total += test.duration;
            }, 0);
            this.outputResults();
          }.bind(this),
          function reject(e) {
            console.error(e);
            this.outputResults();
          }.bind(this)
      );
    },

    runRemainingTests_: function(remainingTests) {
      if (!remainingTests.length)
        return base.Promise.resolve();
      var test = remainingTests.pop();

      // Clear settings storage before each test.
      global.sessionStorage.clear();
      base.Settings.setAlternativeStorageInstance(global.sessionStorage);
      base.onAnimationFrameError =
          testRunners[testType_].onAnimationFrameError.bind(
              testRunners[testType_]);
      base.KeyEventManager.resetInstanceForUnitTesting();

      var testWorkAreaEl_ = document.createElement('div');
      this.resultsEl_.appendChild(testWorkAreaEl_);

      test.workArea = testWorkAreaEl_;
      if (this.setupFn_ !== undefined)
        this.setupFn_.bind(test).call();

      var suite = this;
      return test.run.then(function(ignore) {
        test.status = TestStatus.PASSED;
        suite.testTearDown_(test);
        return suite.runRemainingTests_(remainingTests);
      }, function(error) {
        var stack = error && error.stack ? error.stack : '';
        console.error("Rejected, cause: \'" + error + "\'", stack);
        test.status = TestStatus.FAILED;
        test.failure = error;
        suite.failures_.push({
          error: test.failure,
          test: test.name
        });
        suite.testTearDown_(test);
        return suite.runRemainingTests_(remainingTests);
      });
    },

    testTearDown_: function(test) {
      this.resultsEl_.removeChild(test.workArea);

      if (this.teardownFn_ !== undefined)
        this.teardownFn_.bind(test).call();
    },

    outputResults: function() {
      if ((this.results === TestStatus.PASSED) && showCondensed_ &&
          !this.showLongResults) {
        var parent = this.resultsEl_.parentNode;
        parent.removeChild(this.resultsEl_);
        this.resultsEl_ = undefined;

        parent.appendChild(document.createTextNode('.'));
        return;
      }

      var status = this.resultsEl_.querySelector('.results');
      status.classList.remove('pending');
      if (this.results === TestStatus.PASSED) {
        status.innerText = 'passed';
        status.classList.add('passed');
      } else {
        status.innerText = 'FAILED';
        status.classList.add('failed');
      }

      status.innerText += ' (' + this.duration_.toFixed(2) + 'ms)';

      var child = this.showLongResults ? this.outputLongResults() :
                                         this.outputShortResults();
      if (child !== undefined)
        this.resultsEl_.appendChild(child);
    },

    outputShortResults: function() {
      if (this.results === TestStatus.PASSED)
        return undefined;

      var parent = document.createElement('div');

      var failureList = this.failures;
      for (var i = 0; i < failureList.length; ++i) {
        var fail = failureList[i];

        var preEl = document.createElement('pre');
        preEl.className = 'failure';
        preEl.innerText = 'Test: ' + fail.test + '\n' + fail.error.stack;
        parent.appendChild(preEl);
      }

      return parent;
    },

    outputLongResults: function() {
      var parent = document.createElement('div');

      this.tests_.forEach(function(test) {
        if (this.testsToRun_.length !== 0 &&
            this.testsToRun_.indexOf(test.name) === -1)
          return;

        // Construct an individual result div.
        var testEl = document.createElement('div');
        testEl.className = 'individual-result';

        var link = '/src/tests.html?suite=';
        link += this.name.replace(/\./g, '/');
        link += '&test=' + test.name.replace(/\./g, '/');
        link += '&type=' +
            (testType_ === TestTypes.PERFTEST ? 'perf' : 'unit');

        var suiteInfo = document.createElement('a');
        suiteInfo.href = link;
        suiteInfo.innerText = test.name;
        testEl.appendChild(suiteInfo);

        parent.appendChild(testEl);

        var resultEl = document.createElement('span');
        resultEl.classList.add('results');
        testEl.appendChild(resultEl);
        if (test.status === TestStatus.PASSED) {
          resultEl.classList.add('passed');
          resultEl.innerText =
              'passed (' + test.output() + ')';
        } else if (test.status === TestStatus.PENDING) {
          resultEl.classList.add('failed');
          resultEl.innerText = 'PENDING...TIMEOUT';
        } else {
          resultEl.classList.add('failed');
          resultEl.innerText = 'FAILED';

          var preEl = document.createElement('pre');
          preEl.className = 'failure';
          preEl.innerText = test.failure.stack || test.failure;
          testEl.appendChild(preEl);
        }

        if (test.hasAppendedContent)
          testEl.appendChild(test.appendedContent);
      }.bind(this));

      return parent;
    },

    toString: function() {
      return this.name_;
    }
  };

  function Test(name, test, options) {
    this.name_ = name;
    this.test_ = test;
    this.isPerfTest_ = false;
    this.options_ = options;
    this.failure_ = undefined;
    this.duration_ = 0;
    this.status_ = TestStatus.PENDING;

    this.appendedContent_ = undefined;
  }

  Test.prototype = {
    __proto__: Object.prototype,

    get run() {
      var test = this;
      return new base.Promise(function(r) {
        var startTime = window.performance.now();
        try {
          var maybePromise = test.test_();
          if (maybePromise) {
            // An async test may not have completed.
            maybePromise.then(function(ignored) {
              test.duration = window.performance.now() - startTime;
              r.resolve();
            }, r.reject);
          } else {
            test.duration = window.performance.now() - startTime;
            r.resolve();
          }
        } catch (e) {
          test.duration = window.performance.now() - startTime;
          r.reject(e);
        }
      });
    },

    get failure() {
      return this.failure_;
    },

    set failure(val) {
      this.failure_ = val;
    },

    get name() {
      return this.name_;
    },

    get isPerfTest() {
      return this.isPerfTest_;
    },

    get testRuns() {
      return this.testRuns_;
    },

    get status() {
      return this.status_;
    },

    set status(val) {
      this.status_ = val;
    },

    get duration() {
      return this.duration_;
    },

    get options() {
      return this.options_;
    },

    set duration(duration) {
      this.duration_ = duration;
    },

    get hasAppendedContent() {
      return (this.appendedContent_ !== undefined);
    },

    get appendedContent() {
      return this.appendedContent_;
    },

    get workArea() {
      return this.testWorkArea_;
    },

    set workArea(workArea) {
      this.testWorkArea_ = workArea;
    },

    addHTMLOutput: function(element) {
      this.testWorkArea_.appendChild(element);
      this.appendedContent_ = element;
    },

    toString: function() {
      return this.name_;
    },

    output: function() {
      return this.duration_.toFixed(2) + 'ms';
    }
  };

  function PerfTest(name, test, options) {
    Test.apply(this, arguments);
    this.isPerfTest_ = true;

    var resultObject = options.results || TestResult;
    this.results_ = new resultObject();
  }

  PerfTest.prototype = {
    __proto__: Test.prototype,

    run: function() {
      try {
        this.test_.call(this, this.results_);
        this.status_ = TestStatus.PASSED;
      } catch (e) {
        console.error(e, e.stack);
        this.failure_ = e;
      }
    },

    output: function() {
      return this.results_.output();
    }
  };

  var testRunners = {};
  var totalSuiteCount_ = 0;

  function allSuitesLoaded_() {
    return (testRunners[TestTypes.UNITTEST].suiteCount +
        testRunners[TestTypes.PERFTEST].suiteCount) >= totalSuiteCount_;
  }

  function testSuite(name, suite) {
    testRunners[TestTypes.UNITTEST].addSuite(new TestSuite(name, suite));
    if (allSuitesLoaded_())
      runSuites();
  }

  function perfTestSuite(name, suite) {
    testRunners[TestTypes.PERFTEST].addSuite(new TestSuite(name, suite));
    if (allSuitesLoaded_())
      runSuites();
  }

  function Suites(suitePaths, tests) {
    // Assume one suite per file.
    totalSuiteCount_ = suitePaths.length;

    testRunners[TestTypes.UNITTEST] = new TestRunner(tests);
    testRunners[TestTypes.PERFTEST] = new TestRunner(tests);

    var modules = [];
    suitePaths.forEach(function(path) {
      var moduleName = path.slice(5, path.length - 3);
      moduleName = moduleName.replace(/\//g, '.');
      modules.push(moduleName);
    });
    base.require(modules);
  }

  function runSuites() {
    testRunners[testType_].run();
  }

  function TestResult() {
    this.results_ = [];
  }
  TestResult.prototype = {
    add: function(result) {
      this.results_.push(result);
    },

    output: function() {
      return this.results_.join(', ');
    }
  };

  function TimingTestResult() {
    TestResult.apply(this, arguments);
    this.runCount_ = 0;
  }
  TimingTestResult.prototype = {
    __proto__: TestResult.prototype,

    set testCount(runs) {
      this.runCount_ = runs;
    },

    output: function() {
      var totalTime = 0.0;
      this.results_.forEach(function(t) { totalTime += t; });
      return totalTime.toFixed(2) + 'ms) ' + this.runCount_ + ' runs, ' +
          'avg ' + (totalTime / this.runCount_).toFixed(2) + 'ms/run';
    }
  };

  return {
    showCondensed: showCondensed,
    testType: testType,
    testSuite: testSuite,
    perfTestSuite: perfTestSuite,
    runSuites: runSuites,
    Suites: Suites,

    TestSuite_: TestSuite
  };
});
