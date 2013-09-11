// Copyright (C) 2013:
//    Alex Russell <slightlyoff@chromium.org>
//    Yehuda Katz
//
// Use of this source code is governed by
//    http://www.apache.org/licenses/LICENSE-2.0

// FIXME(slightlyoff):
//    - Document "npm test"
//    - Change global name from "Promise" to something less conflicty
(function(global, browserGlobal, underTest) {
"use strict";

// FIXME(slighltyoff):
//  * aggregates + tests
//  * check on fast-forwarding

underTest = !!underTest;

//
// Async Utilities
//

// Borrowed from RSVP.js
var async;

var MutationObserver = browserGlobal.MutationObserver ||
                       browserGlobal.WebKitMutationObserver;
var Promise;

if (typeof process !== 'undefined' &&
  {}.toString.call(process) === '[object process]') {
  async = function(callback, binding) {
    process.nextTick(function() {
      callback.call(binding);
    });
  };
} else if (MutationObserver) {
  var queue = [];

  var observer = new MutationObserver(function() {
    var toProcess = queue.slice();
    queue = [];
    toProcess.forEach(function(tuple) {
      tuple[0].call(tuple[1]);
    });
  });

  var element = document.createElement('div');
  observer.observe(element, { attributes: true });

  // Chrome Memory Leak: https://bugs.webkit.org/show_bug.cgi?id=93661
  window.addEventListener('unload', function(){
    observer.disconnect();
    observer = null;
  });

  async = function(callback, binding) {
    queue.push([callback, binding]);
    element.setAttribute('drainQueue', 'drainQueue');
  };
} else {
  async = function(callback, binding) {
    setTimeout(function() {
      callback.call(binding);
    }, 1);
  };
}

//
// Object Model Utilities
//

// defineProperties utilities
var _readOnlyProperty = function(v) {
    return {
      enumerable: true,
      configurable: false,
      get: v
    };
};

var _method = function(v, e, c, w) {
    return {
      enumerable:   !!(e || 0),
      configurable: !!(c || 1),
      writable:     !!(w || 1),
      value:           v || function() {}
    };
};

var _pseudoPrivate = function(v) { return _method(v, 0, 1, 0); };
var _public = function(v) { return _method(v, 1); };

//
// Promises Utilities
//

var isThenable = function(any) {
  if (any === undefined)
    return false;
  try {
    var f = any.then;
    if (typeof f == "function") {
      return true;
    }
  } catch (e) { /*squelch*/ }
  return false;
};

var AlreadyResolved = function(name) {
  Error.call(this, name);
};
AlreadyResolved.prototype = Object.create(Error.prototype);

var Backlog = function() {
  var bl = [];
  bl.pump = function(value) {
    async(function() {
      var l = bl.length;
      var x = 0;
      while(x < l) {
        x++;
        bl.shift()(value);
      }
    });
  };
  return bl;
};

//
// Resolver Constuctor
//

var Resolver = function(future,
                        fulfillCallbacks,
                        rejectCallbacks,
                        setValue,
                        setError,
                        setState) {
  var isResolved = false;

  var resolver = this;
  var fulfill = function(value) {
    // console.log("queueing fulfill with:", value);
    async(function() {
      setState("fulfilled");
      setValue(value);
      // console.log("fulfilling with:", value);
      fulfillCallbacks.pump(value);
    });
  };
  var reject = function(reason) {
    // console.log("queuing reject with:", reason);
    async(function() {
      setState("rejected");
      setError(reason);
      // console.log("rejecting with:", reason);
      rejectCallbacks.pump(reason);
    });
  };
  var resolve = function(value) {
    if (isThenable(value)) {
      value.then(resolve, reject);
      return;
    }
    fulfill(value);
  };
  var ifNotResolved = function(func, name) {
    return function(value) {
      if (!isResolved) {
        isResolved = true;
        func(value);
      } else {
        if (typeof console != "undefined") {
          console.error("Cannot resolve a Promise multiple times.");
        }
      }
    };
  };

  // Indirectly resolves the Promise, chaining any passed Promise's resolution
  this.resolve = ifNotResolved(resolve, "resolve");

  // Directly fulfills the future, no matter what value's type is
  this.fulfill = ifNotResolved(fulfill, "fulfill");

  // Rejects the future
  this.reject = ifNotResolved(reject, "reject");

  this.cancel  = function() { resolver.reject(new Error("Cancel")); };
  this.timeout = function() { resolver.reject(new Error("Timeout")); };

  if (underTest) {
    Object.defineProperties(this, {
      _isResolved: _readOnlyProperty(function() { return isResolved; }),
    });
  }

  setState("pending");
};

//
// Promise Constuctor
//

var Promise = function(init) {
  var fulfillCallbacks = new Backlog();
  var rejectCallbacks = new Backlog();
  var value;
  var error;
  var state = "pending";

  if (underTest) {
    Object.defineProperties(this, {
      _value: _readOnlyProperty(function() { return value; }),
      _error: _readOnlyProperty(function() { return error; }),
      _state: _readOnlyProperty(function() { return state; }),
    });
  }

  Object.defineProperties(this, {
    _addAcceptCallback: _pseudoPrivate(
      function(cb) {
        // console.log("adding fulfill callback:", cb);
        fulfillCallbacks.push(cb);
        if (state == "fulfilled") {
          fulfillCallbacks.pump(value);
        }
      }
    ),
    _addRejectCallback: _pseudoPrivate(
      function(cb) {
        // console.log("adding reject callback:", cb);
        rejectCallbacks.push(cb);
        if (state == "rejected") {
          rejectCallbacks.pump(error);
        }
      }
    ),
  });
  var r = new Resolver(this,
                       fulfillCallbacks, rejectCallbacks,
                       function(v) { value = v; },
                       function(e) { error = e; },
                       function(s) { state = s; })
  try {
    if (init) { init(r); }
  } catch(e) {
    r.reject(e);
  }
};

//
// Consructor
//

var isCallback = function(any) {
  return (typeof any == "function");
};

// Used in .then()
var wrap = function(callback, resolver, disposition) {
  if (!isCallback(callback)) {
    // If we don't get a callback, we want to forward whatever resolution we get
    return resolver[disposition].bind(resolver);
  }

  return function() {
    try {
      var r = callback.apply(null, arguments);
      resolver.resolve(r);
    } catch(e) {
      // Exceptions reject the resolver
      resolver.reject(e);
    }
  };
};

var addCallbacks = function(onfulfill, onreject, scope) {
  if (isCallback(onfulfill)) {
    scope._addAcceptCallback(onfulfill);
  }
  if (isCallback(onreject)) {
    scope._addRejectCallback(onreject);
  }
  return scope;
};

//
// Prototype properties
//

Promise.prototype = Object.create(null, {
  "then": _public(function(onfulfill, onreject) {
    // The logic here is:
    //    We return a new Promise whose resolution merges with the return from
    //    onfulfill() or onerror(). If onfulfill() returns a Promise, we forward
    //    the resolution of that future to the resolution of the returned
    //    Promise.
    var f = this;
    return new Promise(function(r) {
      addCallbacks(wrap(onfulfill, r, "resolve"),
                   wrap(onreject, r, "reject"), f);
    });
  }),
  "catch": _public(function(onreject) {
    var f = this;
    return new Promise(function(r) {
      addCallbacks(null, wrap(onreject, r, "reject"), f);
    });
  }),
});

//
// Statics
//

Promise.isThenable = isThenable;

var toPromiseList = function(list) {
  return Array.prototype.slice.call(list).map(Promise.resolve);
};

Promise.any = function(/*...futuresOrValues*/) {
  var futures = toPromiseList(arguments);
  return new Promise(function(r) {
    if (!futures.length) {
      r.reject("No futures passed to Promise.any()");
    } else {
      var resolved = false;
      var firstSuccess = function(value) {
        if (resolved) { return; }
        resolved = true;
        r.resolve(value);
      };
      var firstFailure = function(reason) {
        if (resolved) { return; }
        resolved = true;
        r.reject(reason);
      };
      futures.forEach(function(f, idx) {
        f.then(firstSuccess, firstFailure);
      });
    }
  });
};

Promise.every = function(/*...futuresOrValues*/) {
  var futures = toPromiseList(arguments);
  return new Promise(function(r) {
    if (!futures.length) {
      r.reject("No futures passed to Promise.every()");
    } else {
      var values = new Array(futures.length);
      var count = 0;
      var accumulate = function(idx, v) {
        count++;
        values[idx] = v;
        if (count == futures.length) {
          r.resolve(values);
        }
      };
      futures.forEach(function(f, idx) {
        f.then(accumulate.bind(null, idx), r.reject);
      });
    }
  });
};

Promise.some = function() {
  var futures = toPromiseList(arguments);
  return new Promise(function(r) {
    if (!futures.length) {
      r.reject("No futures passed to Promise.some()");
    } else {
      var count = 0;
      var accumulateFailures = function(e) {
        count++;
        if (count == futures.length) {
          r.reject();
        }
      };
      futures.forEach(function(f, idx) {
        f.then(r.resolve, accumulateFailures);
      });
    }
  });
};

Promise.fulfill = function(value) {
  return new Promise(function(r) {
    r.fulfill(value);
  });
};

Promise.resolve = function(value) {
  return new Promise(function(r) {
    r.resolve(value);
  });
};

Promise.reject = function(reason) {
  return new Promise(function(r) {
    r.reject(reason);
  });
};

//
// Export
//

global.Promise = Promise;

})(this,
  (typeof window !== 'undefined') ? window : {},
  this.runningUnderTest||false);
