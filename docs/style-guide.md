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

## Tests
UI element tests that make sure that an element is instantiable should have
names that start with “`instantiate`”. These tests should, as a general rule,
should not make assertions.

## ES6 features

**Use of all ES6 features is currently prohibited.**

Use of an ES6 feature will be allowed when that feature is supported in
Javascript’s strict mode by both Chrome stable and our current version of D8
(see [here](/third_party/vinn/third_party/v8/README.chromium) for current
version information) and we have ensured that use of the feature won’t break our
downstream dependents. We’re currently running tests to ensure that our
dependents are ES6 compatible.

[This matrix](https://kangax.github.io/compat-table/es6/) gives a good view of
which features are supported in which versions of Chrome.

If you see that Catapult’s version of D8 is behind Chrome stable, use
[this script](/third_party/vinn/bin/update_v8) to update it.

## Workarounds have bugs for removal: Avoid defensive programming

We should never silently eat an unexpected condition. When such a condition
occur we should ensure to output the clearest possible warning or a catastrophic
error if progress cannot continue. If fixing the problem is hard and a simple
patch would allow someone to keep working on a feature, then it is OK to submit
this patch at the express condition that:

  1. An issue is created to track the problem.
  2. The defensive patch is wrapped in a `// TODO` linking to that issue.
  3. The todo and defensive patch are removed after the problem is fixed.

## Issues

Issues should either:

  * Not have a BUG= tag
  * Have a BUG=catapult:#123 bug referring to issue 123 in our github tracker.
  * Have a BUG=chromium:456 bug referring to issue 456 in the chromium tracker.
