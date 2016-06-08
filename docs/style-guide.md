# Catapult Style guide

## Base style guide

Unless stated below, we follow the conventions listed in the [Chromium style
guide](https://www.chromium.org/developers/coding-style) and [Google JavaScript
style guide](http://google.github.io/styleguide/javascriptguide.xml).

## Files
File names `should_look_like_this.html`.

Keep to one concept per file, always. In practice, this usually means one
component or class per file, but can lead to multiple if they’re small and
closely related. If you can, group utility functions into a static class to
clarify their relationship, e.g. `base/statistics.html`.

```
<!-- tracing/model/point.html -->
<script>
‘use strict’;

tr.exportTo(‘tr.model’, function() {
  function Point() {}

  return {
    Point: Point
  };
});
</script>
```

The exception to this rule is when there are multiple small, related classes or
methods. In this case, a file may export multiple symbols:

```
<!-- tracing/base/dom_helpers.html -->
<script>
‘use strict’;

tr.exportTo(‘tr.ui.b’, function() {
  function createSpan() { // … }
  function createDiv() { // … }
  function isElementAttached(element) { // … }

  return {
    createSpan: createSpan,
    createDiv: createDiv,
    isElementAttached: isElementAttached
  };
});
</script>
```

Any tests for a file should be in a file with the same name as the
implementation file, but with a trailing `_test`.

```
touch tracing/model/access_point.html
touch tracing/model/access_point_test.html
```
## Namespacing and element names

All symbols that exist in the global namespace should be exported using the
`exportTo` method.

Exported package names show the file’s location relative to the root `tracing/`
directory. These package names are abbreviated, usually with a 1 or 2 letter
abbreviation - just enough to resolve naming conflicts. All files in the same
directory should share the same package.

```
<!-- tracing/base/units/generic_table.html →
tr.exportTo(‘tr.b.u’, function() {
   // ...
});
```

Polymer element names should use the convention
`hyphenated-package-name-element-name`.

```
<!-- tracing/ui/analysis/counter_sample_sub_view.html -->
<polymer-element name='tr-ui-a-counter-sample-sub-view'>
  ...
</polymer-element>
```

## Classes and objects

Classes should expose public fields only if those fields represent a part of the
class’s public interface.

All fields should be initialized in the constructor. Fields with no reasonable
default value should be initialized to undefined.

Do not set defaults via the prototype chain.

```
function Line() {
  // Good
  this.yIntercept_ = undefined;
}

Line.prototype = {
  // Bad
  xIntercept_: undefined,


  set slope(slope) {
    // Bad: this.slope_ wasn’t initialized in the constructor.
    this.slope_ = slope;
  },

  set yIntercept() {
    // Good
    return this.yIntercept_;
  }
};
```

## Polymer elements
The `<script>` block for the Polymer element can go either inside or outside of
the element’s definition. Generally, the block outside is placed outside when
the script is sufficiently complex that having 2 fewer spaces of indentation
would make it more readable.

```
<polymer-element name="tr-bar">
  <template><div></div></template>
   <script>
     // Can go here...
   </script>
</polymer-element>

<script>
'use strict';
(function(){   // Use this if you need to define constants scoped to that element.
Polymer('tr-bar’, {
  // ... or here.
});
})();
</script>
```

Style sheets should be inline rather than in external .css files.

```
<polymer-element name="tr-bar">
  <style>
  #content {
    display: flex;
  }
  </style>
  <template><div id=”content”></div></template>
</polymer-element>
```

## `undefined` and `null`
Prefer use of `undefined` over `null`.

```
function Line() {
  // Good
  this.yIntercept_ = undefined;
  // Bad
  this.slope = null;
}
```

## Tests
UI element tests that make sure that an element is instantiable should have
names that start with “`instantiate`”. These tests should, as a general rule,
should not make assertions.

## ES6 features

**Use of ES6 features is prohibited unless explicitly approved in the table below.** However, we're currently working to allow them.

| Feature                                                                                                                                     | Status                                                                          |
|---------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------|
| [Arrows](https://github.com/lukehoban/es6features#arrows)                                                                                   | [Approved](https://github.com/catapult-project/catapult/issues/2165) |
| [Classes](https://github.com/lukehoban/es6features#classes)                                                                                 | To be discussed                                                                 |
| [Enhanced object literals](https://github.com/lukehoban/es6features#enhanced-object-literals)                                               | To be discussed                                                                 |
| [Template strings](https://github.com/lukehoban/es6features#template-strings)                                                               | To be discussed                                                                 |
| [Destructuring](https://github.com/lukehoban/es6features#destructuring)                                                                     | To be discussed                                                                 |
| [Default, rest, and spread](https://github.com/lukehoban/es6features#default--rest--spread)                                                 | To be discussed                                                                 |
| [`let` and `const`](https://github.com/lukehoban/es6features#let--const)                                                                    | To be discussed                                                                 |
| [Iterators and `for...of`](https://github.com/lukehoban/es6features#iterators--forof)                                                       | Approved                                                                        |
| [Generators](https://github.com/lukehoban/es6features#generators)                                                                           | Approved                                                                        |
| [Unicode](https://github.com/lukehoban/es6features#unicode)                                                                                 | To be discussed                                                                 |
| [Modules](https://github.com/lukehoban/es6features#modules)                                                                                 | To be discussed                                                                 |
| [Module loaders](https://github.com/lukehoban/es6features#module-loaders)                                                                   | To be discussed                                                                 |
| [`Map`, `Set`, `WeakMap`, and `WeakSet`](https://github.com/lukehoban/es6features#map--set--weakmap--weakset)                               | Approved                                                                        |
| [Proxies](https://github.com/lukehoban/es6features#proxies)                                                                                 | To be discussed                                                                 |
| [Symbols](https://github.com/lukehoban/es6features#symbols)                                                                                 | To be discussed                                                                 |
| [Subclassable Built-ins](https://github.com/lukehoban/es6features#subclassable-built-ins)                                                   | To be discussed                                                                 |
| [Promises](https://github.com/lukehoban/es6features#promises)                                                                               | Approved                                                                        |
| [`Math`, `Number`, `String`, `Array`, and `Object` APIs](https://github.com/lukehoban/es6features#math--number--string--array--object-apis) | To be discussed                                                                 |
| [Binary and octal literals](https://github.com/lukehoban/es6features#binary-and-octal-literals)                                             | To be discussed                                                                 |
| [Reflect API](https://github.com/lukehoban/es6features#reflect-api)                                                                         | To be discussed                                                                 |
| [Tail calls](https://github.com/lukehoban/es6features#tail-calls)                                                                           | To be discussed                                                                 |

### Possible feature statuses
  - **Approved**: this feature is approved for general use.
  - **Testing in progress**: there's agreement that we should use this feature, but we still need to make sure that it's safe. "Testing in progress" statuses should link to a Catapult bug thread tracking the testing.
  - **Discussion in progress**: there's not yet agreement that we should use this feature. "Discussion in progress" statuses should link to a Catapult bug thread about whether the feature should be used.
  - **To be discussed**: this feature hasn't been discussed yet.

Use of an ES6 features shouldn't be considered until that feature is [supported](https://kangax.github.io/compat-table/es6/) in both Chrome stable and [our current version of D8](/third_party/vinn/third_party/v8/README.chromium).

If you see that Catapult’s version of D8 is behind Chrome stable's, use
[this script](/third_party/vinn/bin/update_v8) to update it.

## Avoid defensive programming (and document it when you can't)

Don't silently handle unexpected conditions. When such conditions occur, you
should:

  1. Emit a clear warning and continue if the error is non-catastrophic
  2. Fail loudly if the error is catastrophic

If fixing the problem is hard but a simple workaround is possible, then using
the workaround is OK so long as:

  1. An issue is created to track the problem
  2. The defensive code is wrapped in a `// TODO` linking to the issue
  3. The TODO and defensive code are removed after the problem is fixed

## Issues

Issues should either:

  * Not have a BUG= tag
  * Have a BUG=catapult:#123 bug referring to issue 123 in our github tracker.
  * Have a BUG=chromium:456 bug referring to issue 456 in the chromium tracker.
