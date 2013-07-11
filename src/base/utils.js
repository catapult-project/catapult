// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.iteration_helpers');

base.exportTo('base', function() {
  /**
   * Adds a {@code getInstance} static method that always return the same
   * instance object.
   * @param {!Function} ctor The constructor for the class to add the static
   *     method to.
   */
  function addSingletonGetter(ctor) {
    ctor.getInstance = function() {
      return ctor.instance_ || (ctor.instance_ = new ctor());
    };
  }

  function instantiateTemplate(selector) {
    return document.querySelector(selector).content.cloneNode(true);
  }

  function tracedFunction(fn, name, opt_this) {
    function F() {
      console.time(name);
      try {
        fn.apply(opt_this, arguments);
      } finally {
        console.timeEnd(name);
      }
    }
    return F;
  }

  function normalizeException(e) {
    if (typeof(e) == 'string') {
      return {
        message: e,
        stack: ['<unknown>']
      };
    }

    return {
      message: e.message,
      stack: e.stack ? e.stack : ['<unknown>']
    };
  }

  function stackTrace() {
    var stack = new Error().stack + '';
    stack = stack.split('\n');
    return stack.slice(2);
  }

  return {
    addSingletonGetter: addSingletonGetter,

    tracedFunction: tracedFunction,
    normalizeException: normalizeException,
    instantiateTemplate: instantiateTemplate,
    stackTrace: stackTrace
  };
});

