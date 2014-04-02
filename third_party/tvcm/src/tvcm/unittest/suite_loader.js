// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('tvcm.iteration_helpers');
tvcm.require('tvcm.promise');
tvcm.require('tvcm.unittest.test_suite');

tvcm.exportTo('tvcm.unittest', function() {
  var currentSuiteLoader_ = undefined;
  var hadLoaderFailure_ = false;

  function getAsync(url, cb) {
    return new tvcm.Promise(function(resolver) {
      var req = new XMLHttpRequest();
      req.open('GET', url, true);
      req.onreadystatechange = function(aEvt) {
        if (req.readyState == 4) {
          window.setTimeout(function() {
            if (req.status == 200) {
              resolver.fulfill(req.responseText);
            } else {
              console.log('Failed to load ' + url);
              resolver.reject();
            }
          }, 0);
        }
      };
      req.send(null);
    });
  }

  function TestLink(linkPath, title) {
    this.linkPath = linkPath;
    this.title = title;
  }

  function SuiteLoader(opt_suiteNamesToLoad) {
    if (currentSuiteLoader_)
      throw new Error('Cannot have more than one SuiteLoader active at once');
    currentSuiteLoader_ = this;
    this.numPendingSuites_ = {};
    this.pendingSuiteNames_ = {};

    this.testSuites = [];
    this.testLinks = [];

    this.allSuitesLoadedPromise = new tvcm.Promise(function(r) {
      this.allSuitesLoadedResolver_ = r;
    }.bind(this));

    if (opt_suiteNamesToLoad) {
      this.beginLoadingModules_(opt_suiteNamesToLoad);
    } else {
      getAsync('/tvcm/json/tests').then(
          function(data) {
            var testMetadata = JSON.parse(data);
            var testModuleNames = testMetadata.test_module_names;
            this.beginLoadingModules_(testModuleNames, testMetadata);
          }.bind(this),
          this.loadingTestsFailed_.bind(this));
    }
  }

  var loadedSuitesByName = {};

  SuiteLoader.prototype = {
    beginLoadingModules_: function(testModuleNames, opt_testMetadata) {
      if (opt_testMetadata) {
        var testMetadata = opt_testMetadata;
        for (var i = 0; i < testMetadata.test_links.length; i++) {
          var tl = testMetadata.test_links[i];
          this.testLinks.push(new TestLink(tl['path'],
                                           tl['title']));
        }
      }

      var moduleNamesThatNeedToBeLoaded = [];
      for (var i = 0; i < testModuleNames.length; i++) {
        var name = testModuleNames[i];
        if (loadedSuitesByName[name] === undefined) {
          moduleNamesThatNeedToBeLoaded.push(name);
          continue;
        }
        this.testSuites.push(loadedSuitesByName[name]);
      }

      for (var i = 0; i < moduleNamesThatNeedToBeLoaded.length; i++)
        this.pendingSuiteNames_[moduleNamesThatNeedToBeLoaded[i]] = true;

      // Start the loading.
      if (moduleNamesThatNeedToBeLoaded.length > 0) {
        this.willLoadTests_();
        tvcm.require(moduleNamesThatNeedToBeLoaded);
        this.loadTimeout_ = window.setTimeout(
            this.loadingTestsTimeout_.bind(this),
            60 * 1000);
      } else {
        this.didLoadAllTests_();
      }
    },

    loadingTestsFailed_: function() {
      currentSuiteLoader_ = undefined;
      this.allSuitesLoadedResolver_.reject(
          new Error('/tvcm/json/tests failed to load'));
    },

    loadingTestsTimeout_: function() {
      window.onerror = this.oldWindowOnError_;
      this.oldWindowOnError_ = undefined;

      currentSuiteLoader_ = undefined;
      this.allSuitesLoadedResolver_.reject(
          new Error('Timed out waiting for %s to define suites: ' +
                    tvcm.dictionaryKeys(this.pendingSuiteNames_)));
    },

    get areAllSuitesLoaded() {
      return tvcm.dictionaryLength(this.pendingSuiteNames_) === 0;
    },

    addTestSuite: function(suite) {
      if (this.pendingSuiteNames_[suite.name] === undefined)
        throw new Error('Did not expect to load ' + suite.name);

      loadedSuitesByName[suite.name] = suite;
      delete this.pendingSuiteNames_[suite.name];

      this.testSuites.push(suite);
      if (!this.areAllSuitesLoaded)
        return;
      this.didLoadAllTests_();
    },

    willLoadTests_: function() {
      this.oldWindowOnError_ = window.onerror;
      window.onerror = function(errorMsg, url, lineNumber) {
        this.hadErrorDuringTestLoading_(
            new Error(errorMsg + '\n' + url + ':' + lineNumber));
        if (this.oldWindowOnError_)
          return this.oldWindowOnError_(errorMsg, url, lineNumber);
        return false;
      }.bind(this);
    },

    hadErrorDuringTestLoading_: function(err) {
      window.onerror = this.oldWindowOnError_;
      this.oldWindowOnError_ = undefined;

      if (this.loadTimeout_) {
        window.clearTimeout(this.loadTimeout_);
        this.loadTimeout_ = undefined;
      }

      currentSuiteLoader_ = undefined;
      hadLoaderFailure_ = true; // Lets testSuite adding to fail silently.

      this.allSuitesLoadedResolver_.reject(err);
    },

    didLoadAllTests_: function() {
      window.onerror = this.oldWindowOnError_;
      this.oldWindowOnError_ = undefined;

      if (this.loadTimeout_) {
        window.clearTimeout(this.loadTimeout_);
        this.loadTimeout_ = undefined;
      }

      currentSuiteLoader_ = undefined;
      this.allSuitesLoadedResolver_.resolve(this);
    },

    getAllTests: function() {
      var tests = [];
      this.testSuites.forEach(function(suite) {
        tests.push.apply(tests, suite.tests);
      });
      return tests;
    },

    findTestWithFullyQualifiedName: function(fullyQualifiedName) {
      for (var i = 0; i < this.testSuites.length; i++) {
        var suite = this.testSuites[i];
        for (var j = 0; j < suite.tests.length; j++) {
          var test = suite.tests[j];
          if (test.fullyQualifiedName == fullyQualifiedName)
            return test;
        }
      }
      throw new Error('Test ' + fullyQualifiedName + 'not found');
    }
  };

  function testSuite(name, suiteConstructor) {
    if (currentSuiteLoader_ === undefined) {
      if (hadLoaderFailure_)
        return;
      throw new Error('Cannot define testSuites when no SuiteLoader exists.');
    }
    currentSuiteLoader_.addTestSuite(new tvcm.unittest.TestSuite(
        currentSuiteLoader_, name, suiteConstructor));
  }

  return {
    SuiteLoader: SuiteLoader,
    testSuite: testSuite
  };
});
