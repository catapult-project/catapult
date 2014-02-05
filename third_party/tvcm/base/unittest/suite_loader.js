// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.iteration_helpers');
base.require('base.promise');
base.require('base.unittest.test_suite');

base.exportTo('base.unittest', function() {
  var currentSuiteLoader_ = undefined;

  function getAsync(url, cb) {
    return new base.Promise(function(resolver) {
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

  function SuiteLoader() {
    if (currentSuiteLoader_)
      throw new Error('Cannot have more than one SuiteLoader active at once');
    currentSuiteLoader_ = this;
    this.numPendingSuites_ = {};
    this.pendingSuiteNames_ = {};

    this.testSuites = [];
    this.testLinks = [];

    this.allSuitesLoadedPromise = new base.Promise(function(r) {
      this.allSuitesLoadedResolver_ = r;
    }.bind(this));

    var allTests = getAsync('/base/json/tests').then(
        this.beginLoadingModules_.bind(this),
        this.loadingTestsFailed_.bind(this));
  }

  SuiteLoader.prototype = {
    beginLoadingModules_: function(data) {
      var testMetadata = JSON.parse(data);
      var testModuleNames = testMetadata.test_module_names;

      for (var i = 0; i < testMetadata.test_links.length; i++) {
        var tl = testMetadata.test_links[i];
        this.testLinks.push(new TestLink(tl['path'],
                                         tl['title']));
      }

      for (var i = 0; i < testModuleNames.length; i++)
        this.pendingSuiteNames_[testModuleNames[i]] = true;

      // Start the loading.
      base.require(testModuleNames);
      this.loadTimeout_ = window.setTimeout(
          this.loadingTestsTimeout_.bind(this),
          60 * 1000);
    },

    loadingTestsFailed_: function() {
      currentSuiteLoader_ = undefined;
      this.allSuitesLoadedResolver_.reject(
          new Error('/base/json/tests failed to load'));
    },

    loadingTestsTimeout_: function() {
      currentSuiteLoader_ = undefined;
      this.loadingTestsTimeout_ = undefined;
      this.allSuitesLoadedResolver_.reject(
          new Error('Timed out waiting for %s to define suites: ' +
                    base.dictionaryKeys(this.pendingSuiteNames_)));
    },

    get areAllSuitesLoaded() {
      return base.dictionaryLength(this.pendingSuiteNames_) === 0;
    },

    addTestSuite: function(suite) {
      if (this.pendingSuiteNames_[suite.name] === undefined)
        throw new Error('Did not expect to load ' + suite.name);

      delete this.pendingSuiteNames_[suite.name];

      this.testSuites.push(suite);
      if (!this.areAllSuitesLoaded)
        return;
      this.didLoadAllTests_();
    },

    didLoadAllTests_: function() {
      window.clearTimeout(this.loadTimeout_);
      this.loadTimeout_ = undefined;

      currentSuiteLoader_ = undefined;
      this.allSuitesLoadedResolver_.resolve(this);
    },

    getAllTests: function() {
      var tests = [];
      this.testSuites.forEach(function(suite) {
        tests.push.apply(tests, suite.tests);
      });
      return tests;
    }
  };

  function testSuite(name, suiteConstructor) {
    if (currentSuiteLoader_ === undefined)
      throw new Error('Cannot define testSuites when no SuiteLoader exists.');
    currentSuiteLoader_.addTestSuite(new base.unittest.TestSuite(
        currentSuiteLoader_, name, suiteConstructor));
  }

  return {
    SuiteLoader: SuiteLoader,
    testSuite: testSuite
  };
});
