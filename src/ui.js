// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.exportTo('ui', function() {

  /**
   * Decorates elements as an instance of a class.
   * @param {string|!Element} source The way to find the element(s) to decorate.
   *     If this is a string then {@code querySeletorAll} is used to find the
   *     elements to decorate.
   * @param {!Function} constr The constructor to decorate with. The constr
   *     needs to have a {@code decorate} function.
   */
  function decorate(source, constr) {
    var elements;
    if (typeof source == 'string')
      elements = base.doc.querySelectorAll(source);
    else
      elements = [source];

    for (var i = 0, el; el = elements[i]; i++) {
      if (!(el instanceof constr))
        constr.decorate(el);
    }
  }

  /**
   * Helper function for creating new element for define.
   */
  function createElementHelper(tagName, opt_bag) {
    // Allow passing in ownerDocument to create in a different document.
    var doc;
    if (opt_bag && opt_bag.ownerDocument)
      doc = opt_bag.ownerDocument;
    else
      doc = base.doc;
    return doc.createElement(tagName);
  }

  /**
   * Defines a tracing UI component, a function that can be called to construct
   * the component.
   *
   * Base class:
   * <pre>
   * var List = ui.define('list');
   * List.prototype = {
   *   __proto__: HTMLUListElement.prototype,
   *   decorate: function() {
   *     ...
   *   },
   *   ...
   * };
   * </pre>
   *
   * Derived class:
   * <pre>
   * var CustomList = ui.define('custom-list', List);
   * CustomList.prototype = {
   *   __proto__: List.prototype,
   *   decorate: function() {
   *     ...
   *   },
   *   ...
   * };
   * </pre>
   *
   * @param {string} tagName The tagName of the newly created subtype. If
   *     subclassing, this is used for debugging. If not subclassing, then it is
   *     the tag name that will be created by the component.
   * @param {function=} opt_parentConstructor The parent class for this new
   *     element, if subclassing is desired. If provided, the parent class must
   *     be also a function created by ui.define.
   * @return {function(Object=):Element} The newly created component
   *     constructor.
   */
  function define(tagName, opt_parentConstructor) {
    var createFunction, tagName;
    if (typeof tagName == 'function') {
      throw new Error('Passing functions as tagName is deprecated. Please ' +
                      'use (tagName, opt_parentConstructor) to subclass');
    }

    tagName = tagName.toLowerCase();
    if (opt_parentConstructor) {
      if (!opt_parentConstructor.tagName)
        throw new Error('opt_parentConstructor was not created by ui.define');
      createFunction = opt_parentConstructor;
    } else {
      createFunction = createElementHelper;
    }

    /**
     * Creates a new UI element constructor.
     * @param {Object=} opt_propertyBag Optional bag of properties to set on the
     *     object after created. The property {@code ownerDocument} is special
     *     cased and it allows you to create the element in a different
     *     document than the default.
     * @constructor
     */
    function f(opt_propertyBag) {
      if (opt_parentConstructor &&
          f.prototype.__proto__ != opt_parentConstructor.prototype)
        throw new Error(
            tagName + ' prototye\'s __proto__ field is messed up. ' +
            'It MUST be the prototype of ' + opt_parentConstructor.tagName);

      var el = createFunction(tagName, opt_propertyBag);
      f.decorate(el);
      for (var propertyName in opt_propertyBag) {
        el[propertyName] = opt_propertyBag[propertyName];
      }
      return el;
    }

    /**
     * Decorates an element as a UI element class.
     * @param {!Element} el The element to decorate.
     */
    f.decorate = function(el) {
      el.__proto__ = f.prototype;
      el.componentConstructor = f;
      el.decorate();
    };

    f.tagName = tagName;
    if (opt_parentConstructor)
      f.parentConstructor = opt_parentConstructor;
    f.toString = function() {
      if (!f.parentConstructor)
        return f.tagName;
      return f.parentConstructor.toString() + '::' + f.tagName;
    }

    return f;
  }

  /**
   * Input elements do not grow and shrink with their content. This is a simple
   * (and not very efficient) way of handling shrinking to content with support
   * for min width and limited by the width of the parent element.
   * @param {HTMLElement} el The element to limit the width for.
   * @param {number} parentEl The parent element that should limit the size.
   * @param {number} min The minimum width.
   */
  function limitInputWidth(el, parentEl, min) {
    // Needs a size larger than borders
    el.style.width = '10px';
    var doc = el.ownerDocument;
    var win = doc.defaultView;
    var computedStyle = win.getComputedStyle(el);
    var parentComputedStyle = win.getComputedStyle(parentEl);
    var rtl = computedStyle.direction == 'rtl';

    // To get the max width we get the width of the treeItem minus the position
    // of the input.
    var inputRect = el.getBoundingClientRect();  // box-sizing
    var parentRect = parentEl.getBoundingClientRect();
    var startPos = rtl ? parentRect.right - inputRect.right :
        inputRect.left - parentRect.left;

    // Add up border and padding of the input.
    var inner = parseInt(computedStyle.borderLeftWidth, 10) +
        parseInt(computedStyle.paddingLeft, 10) +
        parseInt(computedStyle.paddingRight, 10) +
        parseInt(computedStyle.borderRightWidth, 10);

    // We also need to subtract the padding of parent to prevent it to overflow.
    var parentPadding = rtl ? parseInt(parentComputedStyle.paddingLeft, 10) :
        parseInt(parentComputedStyle.paddingRight, 10);

    var max = parentEl.clientWidth - startPos - inner - parentPadding;

    function limit() {
      if (el.scrollWidth > max) {
        el.style.width = max + 'px';
      } else {
        el.style.width = 0;
        var sw = el.scrollWidth;
        if (sw < min) {
          el.style.width = min + 'px';
        } else {
          el.style.width = sw + 'px';
        }
      }
    }

    el.addEventListener('input', limit);
    limit();
  }

  /**
   * Takes a number and spits out a value CSS will be happy with. To avoid
   * subpixel layout issues, the value is rounded to the nearest integral value.
   * @param {number} pixels The number of pixels.
   * @return {string} e.g. '16px'.
   */
  function toCssPx(pixels) {
    if (!window.isFinite(pixels))
      console.error('Pixel value is not a number: ' + pixels);
    return Math.round(pixels) + 'px';
  }

  function elementIsChildOf(el, potentialParent) {
    if (el == potentialParent)
      return false;

    var cur = el;
    while (cur.parentNode) {
      if (cur == potentialParent)
        return true;
      cur = cur.parentNode;
    }
    return false;
  };

  return {
    decorate: decorate,
    define: define,
    limitInputWidth: limitInputWidth,
    toCssPx: toCssPx,
    elementIsChildOf: elementIsChildOf
  };
});
