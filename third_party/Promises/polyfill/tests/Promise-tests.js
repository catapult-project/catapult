// Copyright (C) 2013:
//    Alex Russell (slightlyoff@chromium.org)
// Use of this source code is governed by
//    http://www.apache.org/licenses/LICENSE-2.0

(function() {
"use strict";

var t = doh;

//
// Trivial utilities.
//
var log = console.log.bind(console);

var rejected = Promise.reject;
var asyncRejected = function(reason) {
  return new Promise(function(r) {
    setTimeout(r.reject.bind(r, reason), 0);
  });
};

var fulfilled = Promise.fulfill;
var asyncAccepted = function(value) {
  return new Promise(function(r) {
    setTimeout(r.fulfill.bind(r, value), 0);
  });
};

var resolved = Promise.resolve;
var asyncResolved = function(value) {
  return new Promise(function(r) {
    setTimeout(r.resolve.bind(r, value), 0);
  });
};

var pending = function() {
  var resolver;
  var future = new Promise(function(r) { resolver = r; });
  return {
    future: future,
    fulfill: resolver.fulfill,
    reject: resolver.reject,
    resolve: resolver.resolve,
  };
};

var dummy = { dummy: "dummy" };
var sentinel = { sentinel: "sentinel" };
var fulfilledSentinel = fulfilled(sentinel);
var rejectedSentinel = rejected(sentinel);

var async = function(desc, test) {
  return {
    name: desc,
    runTest: function() {
      var d = new doh.Deferred();
      test(d, d.callback.bind(d), d.errback.bind(d));
      return d;
    }
  };
};

t.add("Promise", [
  function prototypeMethods() {
    t.is(typeof Promise.prototype.then, "function");
    t.is(Promise.prototype.then.length, 2);
    t.is(typeof Promise.prototype.catch, "function");
    t.is(Promise.prototype.catch.length, 1);

    var c = 0;
    for(var x in Promise.prototype) { c++; }
    t.is(c, 2);
  },

  function no_arg_ctor() {
    var future = new Promise();
    t.is("pending", future._state);
  },

  function base_state() {
    var resolver;
    t.is(undefined, resolver);
    var future = new Promise(function(r) { resolver = r; });
    t.t(future instanceof Promise);
    t.is(undefined, future._value);
    t.is(undefined, future._error);
    t.is("pending", future._state);
    t.is("object", typeof resolver);
    t.is(false, resolver._isResolved);
  },

  async("Is delivery delayed?", function(d) {
    var resolver;
    var resolved = false;
    var future = new Promise(function(r) { resolver = r; });
    future.then(function(value) {
      resolved = true;
      t.is(true, value);
      d.callback(value);
    });

    t.is(future._state, "pending");
    t.is(false, resolved);
    // t.is(false, resolver._isResolved);
    resolver.resolve(true);
    // FIXME: what should future._value be here?

    t.is("pending", future._state);
    t.is(true, resolver._isResolved);
  }),

  function then_does_not_return_self() {
    var f = new Promise();
    t.t(f.then() !== f);
  },

  function catch_does_not_return_self() {
    var f = new Promise();
    t.t(f.catch() !== f);
  },

  async("Values forward correctly", function(d) {
    var eb = d.errback.bind(d);
    var f = fulfilled(dummy);
    f.then()
     .then(null, eb)
     .then(function(e) {
        t.is(dummy, e);
        d.callback();
     }, eb);
  }),

  async("Errors forward correctly", function(d) {
    var f = rejected("meh");
    f.then(log)
     .then(log, function(e) {
        t.is("meh", e);
        d.callback();
     });
  }),
]);

doh.add("Resolver", [

  function invariants() {
    new Promise(function(r) {
      t.is(r._isResolved, false)
      var isResolvedPD = Object.getOwnPropertyDescriptor(r, "_isResolved");
      t.is("function", typeof isResolvedPD.get);
      t.is("undefined", typeof isResolvedPD.set);
      t.t(isResolvedPD.enumerable);
      t.f(isResolvedPD.configurable);

      t.is("function", typeof r.fulfill);
      t.is("function", typeof r.reject);
      t.is("function", typeof r.resolve);
      t.is("function", typeof r.cancel);
      t.is("function", typeof r.timeout);
    });
  },

  async("cancel", function(d) {
    var resolver;
    var future = new Promise(function(r) {
      try {
        resolver = r;
        t.f(r._isResolved);
        r.cancel();
        t.t(resolver._isResolved);
      } catch(e) {
        d.errback(e);
      }
    });
    t.is("pending", future._state);
    future.then(
      d.errback.bind(d),
      function(e) {
        t.is("object", typeof e);
        t.t(e instanceof Error);
        // FIXME: e doesn't seem to have a .name property!!!
        t.is("Error: Cancel", e.toString());
        d.callback();
      }
    );
    t.t(resolver._isResolved);
    t.is("pending", future._state);
  }),

  async("timeout", function(d) {
    var resolver;
    var future = new Promise(function(r) {
      try {
        resolver = r;
        t.f(r._isResolved);
        r.timeout();
        t.t(resolver._isResolved);
      } catch(e) {
        d.errback(e);
      }
    });
    t.is("pending", future._state);
    future.then(
      d.errback.bind(d),
      function(e) {
        t.is("object", typeof e);
        t.t(e instanceof Error);
        t.is("Error: Timeout", e.toString());
        d.callback();
      }
    );
    t.t(resolver._isResolved);
    t.is("pending", future._state);
  }),

  async("resolve forwards errors", function(d) {
    var e = new Error("synthetic");
    var resolver;
    var f1 = new Promise(function(r) {
      r.reject(e);
    });
    var f2 = new Promise(function(r) {
      r.resolve(f1);
    });
    f2.then(
      d.errback.bind(d),
      function(err) {
        t.is("object", typeof err);
        t.t(err instanceof Error);
        t.is("Error: synthetic", err.toString());
        t.is(e.toString(), err.toString());
        t.is(e, err);
        d.callback();
      }
    );
  }),

  async("resolve forwards values", function(d) {
    var v = new Error("synthetic");
    var resolver;
    var f1 = new Promise(function(r) {
      r.fulfill(v);
    });
    var f2 = new Promise(function(r) {
      r.resolve(f1);
    });
    f2.then(
      function(value) {
        t.is("object", typeof value);
        t.t(value instanceof Error);
        t.is("Error: synthetic", value.toString());
        t.is(v, value);
        d.callback();
      },
      d.errback.bind(d)
    );
  }),

  async("resolve does not forward non futures", function(d) {
    var v = new Error("synthetic");
    var resolver;
    var f1 = new Promise(function(r) {
      r.resolve(v);
    });
    var f2 = new Promise(function(r) {
      r.resolve(f1);
    });
    f2.then(
      function(value) {
        t.is("object", typeof value);
        t.t(value instanceof Error);
        t.is("Error: synthetic", value.toString());
        t.is(v, value);
        d.callback();
      },
      d.errback.bind(d)
    );
  }),

  async("resolve forwards values through then", function(d) {
    var v = new Error("synthetic");
    var resolver;
    var f1 = new Promise(function(r) {
      r.resolve(v);
    });
    var f2 = new Promise(function(r) {
      r.resolve(f1);
    });
    var f3 = f2.then(
      function(value) {
        t.is("object", typeof value);
        t.t(value instanceof Error);
        t.is("Error: synthetic", value.toString());
        t.is(v, value);
        return new Promise(function(r) {
          r.resolve("some other value");
        });
      },
      function(e) { return e; }
    );
    f3.then(
      function(value) {
        t.is("some other value", value);
        d.callback();
      },
      d.errback.bind(d)
    );
  }),

  async("Promises forward through then", function(d, then, error) {
    // FIXME(slightlyoff)
    then();
  }),


  async("isResolved is true while forwarding", function(d) {
    var f1 = pending();
    var r1;
    var f2 = new Promise(function(r) {
      r1 = r;
      r.resolve(f1);
    });
    t.t(r1._isResolved);
    d.callback();
  }),

  async("Throwing in a then callback rejects next.", function(d, then, e) {
    fulfilled(5).then(function(v) {
      throw new Error("Blarg!");
    }).then(e, function(e){then();});
  }),

  //
  // Inspired by the promises-tests repo.
  //
  async("non function rejected callbacks are ignored",
    function(d, then, error) {
      var nonFunction = 10;
      rejected(dummy).then(10, then);
    }
  ),

  async("non function fulfilled callbacks are ignored",
    function(d, then, error) {
      var nonFunction = 10;
      fulfilled(dummy).then(then, 10);
    }
  ),

  // Promise.any

  async("Promise.any fails on no values", function(d, then, error) {
    Promise.any().then(error, then);
  }),

  async("Promise.any succeeds on undefined", function(d, then, error) {
    Promise.any(undefined).then(then, error);
  }),

  async("Promise.any succeeds on raw values", function(d, then, error) {
    Promise.any("thinger", undefined, [], new String("blarg")).then(then, error);
  }),

  async("Promise.any fails on rejected", function(d, then, error) {
    Promise.any(rejected()).then(error, then);
  }),

  async("Promise.any succeeds on fulfilled", function(d, then, error) {
    Promise.any(fulfilled()).then(then, error);
  }),

  async("Promise.any succeeds on fulfilled sentinel", function(d, then, error) {
    Promise.any(fulfilledSentinel).then(then, error);
  }),

  async("Promise.any succeeds on asyncAccepted", function(d, then, error) {
    Promise.any(asyncAccepted()).then(then, error);
  }),

  async("Promise.any succeeds on value + fulfilled", function(d, then, error) {
    Promise.any("thinger", fulfilled(dummy)).then(then, error);
  }),

  async("Promise.any succeeds on fulfilled + rejected", function(d, then, error) {
    Promise.any(fulfilledSentinel, rejectedSentinel).then(then, error);
  }),

  async("Promise.any fails on rejected + fulfilled", function(d, then, error) {
    Promise.any(rejected(dummy), fulfilled("thinger")).then(error, then);
  }),

  async("Promise.any succeeds on pre-fulfilled + pre-rejected",
    function(d, then, error) {
      Promise.any(fulfilledSentinel, rejectedSentinel).then(then, error);
    }
  ),

  async("Promise.any succeeds on value + rejected", function(d, then, error) {
    Promise.any("value", rejected("error")).then(then, error);
  }),

  async("Promise.any succeeds on rejected + value", function(d, then, error) {
    Promise.any(rejectedSentinel, "thinger").then(then, error);
  }),

  // Promise.every

  async("Promise.every fails on no values", function(d, then, error) {
    Promise.every().then(error, then);
  }),

  async("Promise.every succeeds on undefined", function(d, then, error) {
    Promise.every(undefined).then(then, error);
  }),

  async("Promise.every succeeds on raw values", function(d, then, error) {
    Promise.every("thinger", undefined, [], new String("blarg")).then(then, error);
  }),

  async("Promise.every fails on rejected", function(d, then, error) {
    Promise.any(rejected()).then(error, then);
  }),

  async("Promise.every succeeds on fulfilled", function(d, then, error) {
    Promise.every(fulfilled()).then(then, error);
  }),

  async("Promise.every succeeds on asyncAccepted", function(d, then, error) {
    Promise.every(asyncAccepted()).then(then, error);
  }),

  async("Promise.every fails on rejected + value", function(d, then, error) {
    Promise.every(rejected(), "thinger").then(error, then);
  }),

  async("Promise.every fails on asyncRejected + value", function(d, then, error) {
    Promise.every(asyncRejected(), "thinger").then(error, then);
  }),

  async("Promise.every forwards values", function(d, then, error) {
    Promise.every(
      Promise.every(asyncAccepted(5), "thinger").then(function(values) {
        t.is([5, "thinger"], values);
      }),
      Promise.every(asyncAccepted(5), "thinger").then(function(values) {
        t.is([5, "thinger"], values);
      })
    ).then(then, error);
  }),

  async("Promise.every forwards values multiple levels",
    function(d, then, error) {
      Promise.every(asyncResolved(asyncResolved(5)), "thinger")
        .then(function(values) {
          t.is([5, "thinger"], values);
          then();
        }, error);
    }
  ),

  // Promise.some

  async("Promise.some fails on no values", function(d, then, error) {
    Promise.some().then(error, then);
  }),

  async("Promise.some succeeds on undefined", function(d, then, error) {
    Promise.some(undefined).then(then, error);
  }),

  async("Promise.some succeeds on raw values", function(d, then, error) {
    Promise.some("thinger", undefined, [], new String("blarg")).then(then, error);
  }),

  async("Promise.some fails on rejected", function(d, then, error) {
    Promise.some(rejected()).then(error, then);
  }),

  async("Promise.some succeeds on fulfilled", function(d, then, error) {
    Promise.some(fulfilled()).then(then, error);
  }),

  async("Promise.some succeeds on asyncAccepted", function(d, then, error) {
    Promise.some(asyncAccepted()).then(then, error);
  }),

  async("Promise.some succeeds on rejected + fulfilled", function(d, then, error) {
    Promise.some(rejectedSentinel, fulfilledSentinel).then(then, error);
  }),

  async("Promise.some succeeds on value + rejected", function(d, then, error) {
    Promise.some("thinger", rejectedSentinel).then(then, error);
  }),

  // Promise.fulfill

  async("Promise.fulfill is sane", function(d, then, error) {
    Promise.fulfill(sentinel).then(function(v) {
      t.is(sentinel, v);
      then();
    }, error);
  }),

  // FIXME(slightlyoff): MOAR TESTS


  // Promise.resolve

  async("Promise.resolve is sane", function(d, then, error) {
    Promise.resolve(sentinel).then(function(v) {
      t.is(sentinel, v);
      then();
    }, error);
  }),

  // FIXME(slightlyoff): MOAR TESTS


  // Promise.reject

  async("Promise.reject is sane", function(d, then, error) {
    Promise.reject(sentinel).then(error, function(reason) {
      t.is(sentinel, reason);
      then();
    });
  }),

  // FIXME(slightlyoff): MOAR TESTS
]);

})();
