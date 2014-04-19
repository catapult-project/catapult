// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';
tvcm.require('tvcm.unittest');
tvcm.require('tvcm.unittest.suite_loader');
tvcm.require('tvcm.unittest.test_runner');
tvcm.require('tvcm.unittest.html_test_results');

tvcm.requireStylesheet('tvcm.unittest.common');
tvcm.requireTemplate('tvcm.unittest.interactive_test_runner');

tvcm.exportTo('tvcm.unittest', function() {
  /**
   * @constructor
   */
  var InteractiveTestRunner = tvcm.ui.define('x-base-interactive-test-runner');

  InteractiveTestRunner.prototype = {
    __proto__: HTMLUnknownElement.prototype,

    decorate: function() {
      this.allTests_ = undefined;

      this.suppressStateChange_ = false;

      this.testFilterString_ = '';
      this.testTypeToRun_ = tvcm.unittest.TestTypes.UNITTEST;
      this.shortFormat_ = false;
      this.testSuiteName_ = '';

      this.rerunPending_ = false;
      this.runner_ = undefined;
      this.results_ = undefined;

      this.onResultsStatsChanged_ = this.onResultsStatsChanged_.bind(this);
      this.onTestFailed_ = this.onTestFailed_.bind(this);
      this.onTestPassed_ = this.onTestPassed_.bind(this);


      this.appendChild(tvcm.instantiateTemplate(
          '#x-base-interactive-test-runner-template'));

      this.querySelector(
          'input[name=test-type-to-run][value=unit]').checked = true;
      var testTypeToRunEls = tvcm.asArray(this.querySelectorAll(
          'input[name=test-type-to-run]'));

      testTypeToRunEls.forEach(
          function(inputEl) {
            inputEl.addEventListener(
                'click', this.onTestTypeToRunClick_.bind(this));
          }, this);

      var shortFormatEl = this.querySelector('#short-format');
      shortFormatEl.checked = this.shortFormat_;
      shortFormatEl.addEventListener(
          'click', this.onShortFormatClick_.bind(this));
      this.updateShortFormResultsDisplay_();
    },

    set title(title) {
      this.querySelector('#title').textContent = title;
    },

    get allTests() {
      return this.allTests_;
    },

    set allTests(allTests) {
      this.allTests_ = allTests;
      this.scheduleRerun_();
    },

    get testLinks() {
      return this.testLinks_;
    },
    set testLinks(testLinks) {
      this.testLinks_ = testLinks;
      var linksEl = this.querySelector('#links');
      linksEl.textContent = '';
      this.testLinks_.forEach(function(l) {
        var link = document.createElement('a');
        link.href = l.linkPath;
        link.textContent = l.title;
        linksEl.appendChild(link);
      }, this);
    },

    get testFilterString() {
      return this.testFilterString_;
    },

    set testFilterString(testFilterString) {
      this.testFilterString_ = testFilterString;
      this.scheduleRerun_();
      if (!this.suppressStateChange_)
        tvcm.dispatchSimpleEvent(this, 'statechange');
    },

    get shortFormat() {
      return this.shortFormat_;
    },

    set shortFormat(shortFormat) {
      this.shortFormat_ = shortFormat;
      this.querySelector('#short-format').checked = shortFormat;
      if (this.results_)
        this.results_.shortFormat = shortFormat;
      if (!this.suppressStateChange_)
        tvcm.dispatchSimpleEvent(this, 'statechange');
    },

    onShortFormatClick_: function(e) {
      this.shortFormat_ = this.querySelector('#short-format').checked;
      this.updateShortFormResultsDisplay_();
      this.updateResultsGivenShortFormat_();
      if (!this.suppressStateChange_)
        tvcm.dispatchSimpleEvent(this, 'statechange');
    },

    updateShortFormResultsDisplay_: function() {
      var display = this.shortFormat_ ? '' : 'none';
      this.querySelector('#shortform-results').style.display = display;
    },

    updateResultsGivenShortFormat_: function() {
      if (!this.results_)
        return;

      if (this.testFilterString_.length || this.testSuiteName_.length)
        this.results_.showHTMLOutput = true;
      else
        this.results_.showHTMLOutput = false;
      this.results_.showPendingAndPassedTests = this.shortFormat_;
    },

    get testTypeToRun() {
      return this.testTypeToRun_;
    },

    set testTypeToRun(testTypeToRun) {
      this.testTypeToRun_ = testTypeToRun;
      var sel;
      if (testTypeToRun == tvcm.unittest.TestTypes.UNITTEST)
        sel = 'input[name=test-type-to-run][value=unit]';
      else
        sel = 'input[name=test-type-to-run][value=perf]';
      this.querySelector(sel).checked = true;
      this.scheduleRerun_();
      if (!this.suppressStateChange_)
        tvcm.dispatchSimpleEvent(this, 'statechange');
    },

    onTestTypeToRunClick_: function(e) {
      if (e.target.value == 'unit')
        this.testTypeToRun_ = tvcm.unittest.TestTypes.UNITTEST;
      else // e.value == 'perf'
        this.testTypeToRun_ = tvcm.unittest.TestTypes.PERFTEST;
      this.scheduleRerun_();
      if (!this.suppressStateChange_)
        tvcm.dispatchSimpleEvent(this, 'statechange');
    },

    onTestPassed_: function() {
      this.querySelector('#shortform-results').textContent += '.';
    },

    onTestFailed_: function() {
      this.querySelector('#shortform-results').textContent += 'F';
    },

    onResultsStatsChanged_: function() {
      var statsEl = this.querySelector('#stats');
      var stats = this.results_.getStats();
      var numTestsOverall = this.runner_.testCases.length;
      var numTestsThatRan = stats.numTestsThatPassed + stats.numTestsThatFailed;
      statsEl.innerHTML =
          '<span>' + numTestsThatRan + '/' + numTestsOverall +
          '</span> tests run, ' +
          '<span class="unittest-failed">' + stats.numTestsThatFailed +
          '</span> failures, ' +
          ' in ' + stats.totalRunTime.toFixed(2) + 'ms.';
    },

    scheduleRerun_: function() {
      if (this.rerunPending_)
        return;
      if (this.runner_) {
        this.rerunPending_ = true;
        this.runner_.beginToStopRunning();
        var doRerun = function() {
          this.rerunPending_ = false;
          this.scheduleRerun_();
        }.bind(this);
        this.runner_.runCompletedPromise.then(
            doRerun, doRerun);
        return;
      }
      this.beginRunning_();
    },

    beginRunning_: function() {
      var resultsContainer = this.querySelector('#results-container');
      if (this.results_) {
        this.results_.removeEventListener('testpassed',
                                          this.onTestPassed_);
        this.results_.removeEventListener('testfailed',
                                          this.onTestFailed_);
        this.results_.removeEventListener('statschange',
                                          this.onResultsStatsChanged_);
        delete this.results_.getHRefForTestCase;
        resultsContainer.removeChild(this.results_);
      }

      this.results_ = new tvcm.unittest.HTMLTestResults();
      this.results_.getHRefForTestCase = this.getHRefForTestCase.bind(this);
      this.updateResultsGivenShortFormat_();

      this.results_.shortFormat = this.shortFormat_;
      this.results_.addEventListener('testpassed',
                                     this.onTestPassed_);
      this.results_.addEventListener('testfailed',
                                     this.onTestFailed_);
      this.results_.addEventListener('statschange',
                                     this.onResultsStatsChanged_);
      resultsContainer.appendChild(this.results_);

      var tests = this.allTests_.filter(function(test) {
        var i = test.fullyQualifiedName.indexOf(this.testFilterString_);
        if (i == -1)
          return false;
        if (test.testType != this.testTypeToRun_)
          return false;
        return true;
      }, this);

      this.runner_ = new tvcm.unittest.TestRunner(this.results_, tests);
      this.runner_.beginRunning();

      this.runner_.runCompletedPromise.then(
          this.runCompleted_.bind(this),
          this.runCompleted_.bind(this));
    },

    setState: function(state, opt_suppressStateChange) {
      this.suppressStateChange_ = true;
      if (state.testFilterString !== undefined)
        this.testFilterString = state.testFilterString;
      else
        this.testFilterString = '';

      if (state.shortFormat === undefined)
        this.shortFormat = false;
      else
        this.shortFormat = state.shortFormat;

      if (state.testTypeToRun === undefined)
        this.testTypeToRun = tvcm.unittest.TestTypes.UNITTEST;
      else
        this.testTypeToRun = state.testTypeToRun;

      this.testSuiteName_ = state.testSuiteName || '';

      if (!opt_suppressStateChange)
        this.suppressStateChange_ = false;

      this.onShortFormatClick_();
      this.scheduleRerun_();
      this.suppressStateChange_ = false;
    },

    getDefaultState: function() {
      return {
        testFilterString: '',
        testSuiteName: '',
        shortFormat: false,
        testTypeToRun: tvcm.unittest.TestTypes.UNITTEST
      };
    },

    getState: function() {
      return {
        testFilterString: this.testFilterString_,
        testSuiteName: this.testSuiteName_,
        shortFormat: this.shortFormat_,
        testTypeToRun: this.testTypeToRun_
      };
    },

    getHRefForTestCase: function(testCases) {
      return undefined;
    },

    runCompleted_: function() {
      this.runner_ = undefined;
      if (this.results_.getStats().numTestsThatFailed > 0) {
        this.querySelector('#shortform-results').textContent +=
            '[THERE WERE FAILURES]';
      } else {
        this.querySelector('#shortform-results').textContent += '[DONE]';
      }
    }
  };

  return {
    InteractiveTestRunner: InteractiveTestRunner
  };
});
