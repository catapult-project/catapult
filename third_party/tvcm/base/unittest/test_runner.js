// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.raf');

base.exportTo('base.unittest', function() {
  var realBaseOnAnimationFrameError = base.onAnimationFrameError;

  function installGlobalTestHooks(runner) {
    base.onAnimationFrameError = function(error) {
      runner.results.addErrorForCurrentTest(error);
    }
    base.unittest.addHTMLOutputForCurrentTest = function(element) {
      runner.results.addHTMLOutputForCurrentTest(element);
    }

    global.sessionStorage.clear();
    base.Settings.setAlternativeStorageInstance(global.sessionStorage);
    base.KeyEventManager.resetInstanceForUnitTesting();
  }

  function uninstallGlobalTestHooks() {
    base.onAnimationFrameError = realBaseOnAnimationFrameError;
    base.unittest.addHTMLOutputForCurrentTest = undefined;
  }


  function TestRunner(results, testCases) {
    this.results_ = results;
    this.testCases_ = testCases;
    this.pendingTestCases_ = [];

    this.runOneTestCaseScheduled_ = false;

    this.runCompletedPromise = undefined;
    this.runCompletedResolver_ = undefined;

    this.currentTestCase_ = undefined;
  }

  TestRunner.prototype = {
    __proto__: Object.prototype,

    beginRunning: function() {
      if (this.pendingTestCases_.length)
        throw new Error('Tests still running!');

      this.runCompletedPromise = new base.Promise(function(resolver) {
        this.runCompletedResolver_ = resolver;
      }.bind(this));

      this.pendingTestCases_ = this.testCases_.slice(0);

      this.scheduleRunOneTestCase_();

      return this.runCompletedPromise;
    },

    beginToStopRunning: function() {
      if (!this.runCompletedResolver_)
        throw new Error('Still running');
      this.pendingTestCases_ = [];
      return this.runCompletedPromise;
    },

    get testCases() {
      return this.testCases_;
    },

    get results() {
      return this.results_;
    },

    scheduleRunOneTestCase_: function() {
      if (this.runOneTestCaseScheduled_)
        return;
      this.runOneTestCaseScheduled_ = true;
      base.requestIdleCallback(this.runOneTestCase_, this);
    },

    runOneTestCase_: function() {
      this.runOneTestCaseScheduled_ = false;

      if (this.pendingTestCases_.length == 0) {
        this.didFinishRunningAllTests_();
        return;
      }

      this.currentTestCase_ = this.pendingTestCases_.splice(0, 1)[0];

      this.results_.willRunTest(this.currentTestCase_);
      if (!this.setUpCurrentTestCase_()) {
        this.results_.didCurrentTestEnd();
        this.currentTestCase_ = undefined;
        this.scheduleRunOneTestCase_();
        return;
      }

      this.runCurrentTestCase_().then(
          function pass(result) {
            this.tearDownCurrentTestCase_(true);
            if (result)
              this.results_.setReturnValueFromCurrentTest(result);
            this.results_.didCurrentTestEnd();
            this.currentTestCase_ = undefined;
            this.scheduleRunOneTestCase_();
          }.bind(this),
          function fail(error) {
            this.results_.addErrorForCurrentTest(error);
            this.tearDownCurrentTestCase_(false);
            this.results_.didCurrentTestEnd();
            this.currentTestCase_ = undefined;
            this.scheduleRunOneTestCase_();
          }.bind(this));
    },

    setUpCurrentTestCase_: function() {
      // Try setting it up. Return true if succeeded.
      installGlobalTestHooks(this);
      try {
        if (this.currentTestCase_.options_.setUp)
          this.currentTestCase_.options_.setUp.call(this.currentTestCase_);
      } catch (error) {
        this.results_.addErrorForCurrentTest(error);
        return false;
      }
      return true;
    },

    runCurrentTestCase_: function() {
      return new Promise(function(runTestCaseResolver) {
        try {
          var maybePromise = this.currentTestCase_.run();
        } catch (error) {
          runTestCaseResolver.reject(error);
          return;
        }

        if (maybePromise !== undefined && maybePromise.then) {
          maybePromise.then(
              function(result) {
                runTestCaseResolver.fulfill(result);
              },
              function(error) {
                runTestCaseResolver.reject(error);
              });
        } else {
          runTestCaseResolver.fulfill(maybePromise);
        }
      }.bind(this));
    },

    tearDownCurrentTestCase_: function() {
      try {
        if (this.currentTestCase_.tearDown)
          this.currentTestCase_.tearDown.call(this.currentTestCase_);
      } catch (error) {
        this.results_.addErrorForCurrentTest(error);
      }

      uninstallGlobalTestHooks();
    },

    didFinishRunningAllTests_: function() {
      this.results.didRunTests();
      this.runCompletedResolver_.resolve();
      this.runCompletedResolver_ = undefined;
    }
  };

  return {
    TestRunner: TestRunner
  };
});
