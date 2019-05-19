<!-- Copyright 2018 The Chromium Authors. All rights reserved.
     Use of this source code is governed by a BSD-style license that can be
     found in the LICENSE file.
-->

# Chromeperf Frontend Architecture

This document outlines the MVC architecture of the chromeperf.appspot.com v2.0
frontend.

## Model-View-Controller Pattern

The V1 `/report`, `/group_report`, `/alerts`, and `/speed_releasing` pages were
each relatively complex, implementing many features to support several related
but distinct use cases.

The V2 UI merges all of those pages into a Single Page App in order to support
all of their use cases and more simultaneously. It supports many features using
many types of web components with a significant amount of state. Nearly all of
that state is managed with Redux: data from the server, form data, display data
such as scalars and lines, intermediate data, etc. Pure reducer functions are
easy to read, maintain, and test, so it makes sense to use them as much as
possible in order to prevent the side-effecting tangles that accumulated in the
V1 UI.

There are many ways to interpret the Model-View-Controller pattern. One of the
open questions is this: how closely should the Model reflect the View (or vice
versa)? Should there be exactly 1 Model component per View component, or should
the Model be idealized and separate from the requirements of the View? How we
answer this question affects how we design the framework.

Since V2SPA manages form data, display data, and intermediate data as well as
served data using Redux, it takes a middle ground. Generally, a close
relationship between Model components and View components can greatly simplify
maintenance and debugging. However, some important pieces of data must be
centralized so they can be shared between many View components.

Centralizing data in a Redux store with Polymer-Redux across the entire app is
as simple as the tutorial.
```
class FooView extends ElementBase {
  static get properties() {
    return {
      userEmail: {statePath: 'userEmail'},
    };
  }
}
function updateUserEmailReducer(state, {userEmail}) {
  return {...state, userEmail};
}
```

However, maintaining a separate Model component for each View component requires
a little more machinery. Polymer-Redux allows statePath to be a selector
function, which helps, but doesn’t quite take us all the way.

When a Redux app only contains a single array of many todos, actions can
identify a particular todo using a [single
index](https://redux.js.org/recipes/structuringreducers/immutableupdatepatterns#updating-an-item-in-an-array).
However, the DOM tree in V2SPA can grow quite deep, with many nested arrays and
corresponding dom-repeats. Passing many indices quickly grows cumbersome, so
V2SPA extends the statePath concept as demonstrated by
[uniflow](https://google.github.io/uniflow-polymer/). Most View components have
a single statePath String property bound from their parent. This dot-separated
path points to a Model component (object) in the state tree that contains all of
the state needed to render that View component. statePath String properties are
used both to access data in the state tree for rendering (using Polymer-Redux’s
statePath() selector functions), and to update the state via Redux actions.
State path properties need not be named exactly statePath: V2SPA also contains
linkedStatePath and rootStatePath, but they are all just dot-separated String
properties that point to Model components. This flexibility allows for a
many-to-many relationship between View components and Model components.

```
<foo-view state-path="[[statePath]].foo"></foo-view>

class FooView extends ElementBase {
  static get properties() {
    return {
      statePath: {type: String},
      isEnabled: {
        type: Boolean,
        statePath(state) {
          return Polymer.Path.get(state, this.statePath).isEnabled);
        },
    };
  }
  onToggleIsEnabled_(event) {
    STORE.dispatch('toggleIsEnabled', this.statePath);
  }
}
const TOGGLE_IS_ENABLED = 'FooView.TOGGLE_IS_ENABLED';
FooView.actions = {
  toggleIsEnabled: statePath => {
    return {type: TOGGLE_IS_ENABLED, statePath};
  },
};
function toggleIsEnabledReducer(rootState, {statePath}) {
  return setImmutable(rootState, statePath, localState => {
    return {...localState, isEnabled: !localState.isEnabled};
  });
}
function reducer(state, action) {
  switch (action.type) {
    case TOGGLE_IS_ENABLED: return toggleIsEnabledReducer(state, action);
  }
}
```

There’s a lot of boilerplate there, so V2SPA uses some helpers to reduce it.

 * statePathProperties(‘statePath’, {isEnabled: {type: Boolean}})
   returns the Polymer-Redux property descriptors with the statePath: {type:
   String} property and with the statePath() selector functions. Parameterizing
   the statePathPropertyName allows View components to bind properties from
   multiple different Model components, which is occasionally necessary.
 * renameReducer(prefix, reducer) prepends the View component name to the
   reducer function name so that actions can set type: reducerFunction.name. 
 * registerReducer(reducer) builds a single global Map from action types (which
   are reducer names) to case functions, as per the [example in the Redux
   docs](https://redux.js.org/recipes/reducingboilerplate#generating-reducers).
 * statePathReducer(reducer) wraps a case function in
   setImmutable().
 * ElementBase.register(FooView) wraps customElements.define(), renames the
   reducers, wraps them with statePathReducer, and registers them.

Here is the above example rewritten using these helpers.
```
class FooView extends ElementBase {
  static get properties() {
    return {
      statePath: String,
      isEnabled: Boolean,
    };
  }
  onToggleIsEnabled_(event) {
    STORE.dispatch(TOGGLE(this.statePath + '.isEnabled'));
  }
}
ElementBase.register(FooView);
```

(In practice, action creators and reducers contain much more involved logic, but
registering and calling them are as simple as that. statePathProperties and
event listeners are as simple as that.)

Using reducer names as action types eliminates action type name boilerplate at
the cost of the ability to have multiple reducers respond to the same action
type, though that hasn’t been an issue. Prefixing reducer names effectively
namespaces them to their View component, allowing the app to collect all
reducers for all View components into a single Map. This allows each View
component to be fully responsible for rendering and updating its own state. It
doesn’t need to worry about action type name collisions with other View
components. It doesn’t need to worry about calling its childrens’ reducers, nor
hope that its parent calls its own reducers properly.
