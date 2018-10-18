[![Build status](https://travis-ci.org/PolymerElements/iron-dropdown.svg?branch=master)](https://travis-ci.org/PolymerElements/iron-dropdown)

_[Demo and API docs](https://elements.polymer-project.org/elements/iron-dropdown)_


## &lt;iron-dropdown&gt;

`<iron-dropdown>` is a generalized element that is useful when you have
hidden content (`dropdown-content`) that is revealed due to some change in
state that should cause it to do so.

Note that this is a low-level element intended to be used as part of other
composite elements that cause dropdowns to be revealed.

Examples of elements that might be implemented using an `iron-dropdown`
include comboboxes, menubuttons, selects. The list goes on.

The `<iron-dropdown>` element exposes attributes that allow the position
of the `dropdown-content` relative to the `dropdown-trigger` to be
configured.

```html
<iron-dropdown horizontal-align="right" vertical-align="top">
  <div slot="dropdown-content">Hello!</div>
</iron-dropdown>
```

In the above example, the `<div>` assigned to the `dropdown-content` slot will be
hidden until the dropdown element has `opened` set to true, or when the `open`
method is called on the element.

### Changes in 2.0
- Removed the private property `_focusTarget` which was deprecated.
- `neon-animation 2.0` doesn't import the Web Animations polyfill, so you'll have to import it ([see example](demo/index.html))
