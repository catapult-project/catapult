// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('ui.trace_viewer');
base.requireStylesheet('base.unittest');
base.require('base.settings');
base.require('base.unittest.test_error');
base.require('base.unittest.assertions');

base.exportTo('base.unittest', function() {
  var TestResults = {
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
    if (val === 'perf-test')
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

  function TestRunner(suitePaths, tests) {
    this.suitePaths_ = suitePaths || [];
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
      this.clear_(document.querySelector('#message-list'));

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
      suite.runTests(this.tests_);

      this.stats_.duration += suite.duration;
      this.stats_.tests += suite.testCount;
      this.stats_.failures += suite.failureCount;

      this.updateStats_();

      // Give the view time to update.
      window.setTimeout(function() {
        this.runSuites_(idx + 1);
      }.bind(this), 1);
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
          ' in ' + this.stats_.duration + 'ms.';
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
    this.results_ = TestResults.PENDING;
    this.showLongResults = false;
    this.duration_ = 0.0;
    this.resultsEl_ = undefined;
    this.setupOnceRan_ = false;

    global.setupOnce = function(fn) { this.setupOnceFn_ = fn; }.bind(this);
    global.setup = function(fn) { this.setupFn_ = fn; }.bind(this);
    global.teardown = function(fn) { this.teardownFn_ = fn; }.bind(this);

    global.test = function(name, test) {
      if (this.testNames_[name] === true)
        logWarningMessage('Duplicate test name detected: ' + name);

      this.tests_.push(new Test(name, test));
      this.testNames_[name] = true;
    }.bind(this);

    global.perfTest = function(name, testRuns, test) {
      if (this.testNames_[name] === true)
        logWarningMessage('Duplicate test name detected: ' + name);

      this.tests_.push(new PerfTest(name, test, testRuns));
      this.testNames_[name] = true;
    }.bind(this);

    suite.call();

    global.setupOnce = undefined;
    global.setup = undefined;
    global.teardown = undefined;
    global.test = undefined;
    global.perf_test = undefined;
  }

  TestSuite.prototype = {
    __proto__: Object.prototype,

    get name() {
      return this.name_;
    },

    get results() {
      return this.results_;
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

      var start = new Date().getTime();
      this.results_ = TestResults.PENDING;
      this.tests_.forEach(function(test) {
        if (this.testsToRun_.length !== 0 &&
            this.testsToRun_.indexOf(test.name) === -1)
          return;

        if (!this.setupOnceRan_ && this.setupOnceFn_ !== undefined) {
          this.setupOnceFn_();
          this.setupOnceRan_ = true;
        }

        for (var testIterationIndex = 0;
             testIterationIndex < test.testRuns.length;
             ++testIterationIndex) {
          var runCount = test.testRuns[testIterationIndex];

          // Clear settings storage before each test.
          global.sessionStorage.clear();
          base.Settings.setAlternativeStorageInstance(global.sessionStorage);
          base.onAnimationFrameError =
              testRunners[testType_].onAnimationFrameError.bind(
                  testRunners[testType_]);

          if (this.setupFn_ !== undefined)
            this.setupFn_.bind(test).call();

          var testWorkAreaEl_ = document.createElement('div');

          this.resultsEl_.appendChild(testWorkAreaEl_);

          var individualStart = new Date().getTime();
          for (var c = 0; c < runCount; ++c)
            test.run(testWorkAreaEl_);
          test.duration[runCount] = new Date().getTime() - individualStart;

          this.resultsEl_.removeChild(testWorkAreaEl_);

          if (this.teardownFn_ !== undefined)
            this.teardownFn_.bind(test).call();

          if (test.result === TestResults.FAILED) {
            this.failures_.push({
              error: test.failure,
              test: test.name
            });
            this.results_ = TestResults.FAILED;
          }
        }
      }, this);

      if (this.results_ === TestResults.PENDING)
        this.results_ = TestResults.PASSED;

      this.duration_ = new Date().getTime() - start;
      this.outputResults();
    },

    outputResults: function() {
      if ((this.results === TestResults.PASSED) && showCondensed_ &&
          !this.showLongResults) {
        var parent = this.resultsEl_.parentNode;
        parent.removeChild(this.resultsEl_);
        this.resultsEl_ = undefined;

        parent.appendChild(document.createTextNode('.'));
        return;
      }

      var status = this.resultsEl_.querySelector('.results');
      status.classList.remove('pending');
      if (this.results === TestResults.PASSED) {
        status.innerText = 'passed';
        status.classList.add('passed');
      } else {
        status.innerText = 'FAILED';
        status.classList.add('failed');
      }

      status.innerText += ' (' + this.duration_ + 'ms)';

      var child = this.showLongResults ? this.outputLongResults() :
                                         this.outputShortResults();
      if (child !== undefined)
        this.resultsEl_.appendChild(child);
    },

    outputShortResults: function() {
      if (this.results === TestResults.PASSED)
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

        for (var i = 0; i < test.testRuns.length; ++i) {
          var runCount = test.testRuns[i];

          // Construct an individual result div.
          var testEl = document.createElement('div');
          testEl.className = 'individual-result';

          var link = '/src/tests.html?suite=';
          link += this.name.replace(/\./g, '/');
          link += '&test=' + test.name.replace(/\./g, '/');

          var suiteInfo = document.createElement('a');
          suiteInfo.href = link;
          suiteInfo.innerText = test.name;
          testEl.appendChild(suiteInfo);

          parent.appendChild(testEl);

          var resultEl = document.createElement('span');
          resultEl.classList.add('results');
          testEl.appendChild(resultEl);
          if (test.result === TestResults.PASSED) {
            resultEl.classList.add('passed');
            resultEl.innerText = 'passed (' + test.duration[runCount] + 'ms)';
          } else {
            resultEl.classList.add('failed');
            resultEl.innerText = 'FAILED';

            var preEl = document.createElement('pre');
            preEl.className = 'failure';
            preEl.innerText = test.failure.stack;
            testEl.appendChild(preEl);
          }

          if (runCount !== 1) {
            var averageTime = test.duration[runCount] / runCount;
            resultEl.innerText += ' (' + runCount + ' runs, ';
            resultEl.innerText += 'avg ' + averageTime + 'ms/run)';
          }

          if (test.hasAppendedContent)
            testEl.appendChild(test.appendedContent);
        }
      }.bind(this));

      return parent;
    },

    toString: function() {
      return this.name_;
    }
  };

  function Test(name, test) {
    this.name_ = name;
    this.test_ = test;
    this.isPerfTest_ = false;
    this.testRuns_ = [1];
    this.result_ = TestResults.FAILED;
    this.failure_ = undefined;
    this.duration_ = {};

    this.appendedContent_ = undefined;
  }

  Test.prototype = {
    __proto__: Object.prototype,

    run: function(workArea) {
      this.testWorkArea_ = workArea;
      try {
        this.test_.bind(this).call();
        this.result_ = TestResults.PASSED;
      } catch (e) {
        console.error(e, e.stack);
        this.failure_ = e;
      }
    },

    get failure() {
      return this.failure_;
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

    get result() {
      return this.result_;
    },

    set result(val) {
      this.result_ = val;
    },

    get duration() {
      return this.duration_;
    },

    get hasAppendedContent() {
      return (this.appendedContent_ !== undefined);
    },

    get appendedContent() {
      return this.appendedContent_;
    },

    addHTMLOutput: function(element) {
      this.testWorkArea_.appendChild(element);
      this.appendedContent_ = element;
    },

    toString: function() {
      return this.name_;
    }
  };

  function PerfTest(name, test, testRuns) {
    Test.apply(this, arguments);
    this.isPerfTest_ = true;
    this.testRuns_ = testRuns;
  }

  PerfTest.prototype = {
    __proto__: Test.prototype
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

  return {
    showCondensed: showCondensed,
    testType: testType,
    testSuite: testSuite,
    perfTestSuite: perfTestSuite,
    runSuites: runSuites,
    Suites: Suites
  };
});
