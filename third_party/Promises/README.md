#### NOTE: The IDL hosted here is now advisory. This repo hosts refactoring examples and designs, a high-fidelity polyfill, and rationale for this work. [See the living DOM spec for the current version](http://dom.spec.whatwg.org/#futures) if you are implementing Promises in a runtime.

<img src="http://promises-aplus.github.com/promises-spec/assets/logo-small.png"
     align="right" alt="Promises/A+ logo, since DOMFutures are compatible" />

# DOM Promises

A Promises Design for DOM, currently in IDL. Also a p(r)ollyfill
and re-worked APIs to take advantage of the new semantics.

## Promises? [I Don't Speak Your Crazy Moon Language](http://www.pigdog.org/auto/mr_bads_list/shortcolumn/1914.html).

A Promise is an object that implements a standard contract for
the results of an operation that may have already occurred or may happen in the
future.

There's a lot in that sentence that's meaningful, but the big ticket items are:

  * Promises are a contract for _a single result_, either success or failure. If
    you need to model something that happens multiple times, a single Future is
    not the answer (try events or an iterator that creates a stream of Promises).
  * Promises provide a mechanism for multiple parties to be informed of a value,
    much the same way many bits of code can hold a reference to a variable
    without knowing about each other.
  * Promises aren't, in themselves notable. Instead, they derive their value
    through being _the one way_ to encapsulate potentially asynchronous return
    values.

To do all of this without syntax support from the language, Promises must be
objects with standardized methods. The current design provides a constructable 
class that allows end-user code to vend instances of `Future` from their own APIs 
as well as a few standard methods:

```js
// Accepts "accept" and "reject" callbacks, roughly the same thing as success
// and failure for the operation.
futureInstance.then(onaccept, onreject);

// Accept and reject callbacks only ever have a single parameter, which is the
// value or reason, respectively:
futureInstance.then(
  function(value) {
    doSomethingWithTheResult(value);
  },
  function(reason) { console.error(reason); }
);

// .then() always returns a new Future, one which takes whatever value the
// callback it's registered with returns:
futureInstance.then(function(value) {
                return processValue(value);
              })
              .then(function(processedValue) {
                // ...
              });

// A key part of the Futures design is that these operations are *chainable*,
// even for asynchronous code. This makes it easy to compose asynchronous
// operations in readable, linear-looking code:
futureInstance.then(aHandlerThatReturnsAFuture)
              .then(doSomethingAfterTheSecondCallback);

// .catch() gives you access only to errors:
futureInstance.catch(onreject);
```

## OK, So Why Promises For DOM?

To understand why DOM needs Futures, think about a few of the asynchronous APIs
in DOM that return single values:

  * [XHR](https://developer.mozilla.org/en-US/docs/DOM/XMLHttpRequest)
  * [Geolocation](http://www.w3.org/TR/geolocation-API/)
  * [IndexedDB](http://www.w3.org/TR/IndexedDB/)
  * [`onload`](https://developer.mozilla.org/en-US/docs/DOM/window.onload)

There are some similarities today in how these APIs work. XHR and `onload` share 
the idea of a `readyState` property to let code detect if something has happened 
in the past, giving rise to logic like this:

```js
if (document.readyState == "complete") {
  doStartupWork();
} else {
  document.addEventListener("load", doStartupWork, false);
}
```

This is cumbersome and error-prone, not to mention ugly. IndexedDB's
[`IDBRequest` class](https://developer.mozilla.org/en-US/docs/IndexedDB/IDBRequest) 
also supports a `readyState` property, but the values range from 
[1-2](https://developer.mozilla.org/en-US/docs/IndexedDB/IDBRequest#readyState_constants), 
not [0-4 as used in XHR](https://developer.mozilla.org/en-US/docs/DOM/XMLHttpRequest#Properties) 
or [strings as used for documents](http://www.whatwg.org/specs/web-apps/current-work/multipage/dom.html#current-document-readiness). 
Making matters worse, the callback and event names don't even match! Clearly 
DOM needs a better way to do things.

A uniform interface would allow us to manage our callbacks sanely across APIs:

```js
// Example of what the future might hold, not in any current spec
document.ready().then(doStartupWork);

// By returning a Future subclass, XHR's send() method gets more usable too:
var xhr = new XMLHttpRequest();
xhr.open("GET", filename, true);
xhr.send().then(handleSuccessfulResponse,
                handleErrorResponse);

// Geolocation can be easily refactored too:
navigator.geolocation.getCurrentPosition().then(successCallback, errorCallback);

// Even IDB gets saner:
indexedDB.open(databaseName).then(function(db) {
  // ...
});
```

Providing a single abstraction for this sort of operation creates cross-cutting
value across specifications, making it easier to use DOM and simpler for
libraries to interoperate based on a standard design.

## OK, But Aren't You Late To This Party?

There's a [long, long history of Promises](http://en.wikipedia.org/wiki/Futures_and_promises)
both inside and outside JavaScript. Many other languages provide them via
language syntax or standard library. Promises are such a common pattern inside
JavaScript that nearly all major libraries provide some form them and vend 
them for many common operations which they wrap. There are  differences in 
terminology and use, but the core ideas are mostly the same be they 
[jQuery Deferreds](http://api.jquery.com/category/deferred-object/), 
[WinJS Promises](http://msdn.microsoft.com/en-us/library/windows/apps/br211867.aspx), 
[Dojo Deferreds or Promises](http://dojotoolkit.org/documentation/tutorials/1.6/promises/), 
[Cujo Promises](https://github.com/cujojs/when), 
[Q Promises](https://github.com/kriskowal/q/wiki/API-Reference), [RSVP Promises (used heavily in Ember)](https://github.com/tildeio/rsvp.js), or even in [Node Promises](https://github.com/kriszyp/node-promise). The diversity of implementations has led both to incompatibility and efforts to standardize, the most promising of which is the [Promises/A+ effort](https://github.com/promises-aplus/promises-spec), which of course differs slightly from [Promises/A](http://wiki.commonjs.org/wiki/Promises/A) and greatly from [other pseudo-standard variants proposed over the years](http://wiki.commonjs.org/wiki/Promises). 

Promises/A+ doesn't define all of the semantics needed for a full implementation, 
and if we assume DOM needs Promises, it will also need an answer to those 
questions. That's what this repository is about.

## More Examples

```js
// New APIs that vend Futures are easier to reason about. Instead of:
if (document.readyState == "complete") {
  doStartupWork();
} else {
  document.addEventListener("load", doStartupWork, false);
}

// ...a Future-vending ready() method can be used at any time:
document.ready().then(doStartupWork);

// Like other Promises-style APIs, .then() and .done() are the
// primary way to work with Futures, including via chaining, in
// this example using an API proposed at:
//    https://github.com/slightlyoff/async-local-storage
var storage = navigator.storage;
storage.get("item 1").then(function(item1value) {
  return storage.set("item 1", "howdy");
}).
done(function() {
  // The previous future is chained to not resolve until
  //item 1 is set to "howdy"
  storage.get("item 1").done(console.log);
});
```

Promises can also be new'd up and used in your own APIs, making them a powerful
abstraction for building asynchronous contracts for single valued operations;
basically any time you want to do some work asynchronously but only care about
a single response value:

```js
function fetchJSON(filename) {
  // Return a Promise that represents the fetch:
  return new Promise(function(resolver){
    // The resolver is how a Promise is satisfied. It has reject(), fulfill(),
    // and resolve() methods that your code can use to inform listeners with:
    var xhr = new XMLHttpRequest();
    xhr.open("GET", filename, true);
    xhr.send();
    xhr.onreadystatechange = function() {
      if (xhr.readyState == 4) {
        try {
          resolver.resolve(JSON.parse(xhr.responseText));
        } catch(e) {
          resolver.reject(e);
        }
      }
    }
  });
}

// Now we can use the uniform Future API to reason about JSON fetches:
fetchJSON("thinger.json").then(function(object) { ... } ,
                               function(error) { ... });
```
