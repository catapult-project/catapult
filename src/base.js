// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';


/**
 * The global object.
 * @type {!Object}
 * @const
 */
var global = this;


/** Platform, package, object property, and Event support. */
this.base = (function() {

  /**
   * Base path for modules. Used to form URLs for module 'require' requests.
   */
  var moduleBasePath = '.';
  function setModuleBasePath(path) {
    if (path[path.length - 1] == '/')
      path = path.substring(0, path.length - 1);
    moduleBasePath = path;
  }


  function mLog(text, opt_indentLevel) {
    if (true)
      return;

    var spacing = '';
    var indentLevel = opt_indentLevel || 0;
    for (var i = 0; i < indentLevel; i++)
      spacing += ' ';
    console.log(spacing + text);
  }

  /**
   * Builds an object structure for the provided namespace path,
   * ensuring that names that already exist are not overwritten. For
   * example:
   * 'a.b.c' -> a = {};a.b={};a.b.c={};
   * @param {string} name Name of the object that this file defines.
   * @param {*=} opt_object The object to expose at the end of the path.
   * @param {Object=} opt_objectToExportTo The object to add the path to;
   *     default is {@code global}.
   * @private
   */
  function exportPath(name, opt_object, opt_objectToExportTo) {
    var parts = name.split('.');
    var cur = opt_objectToExportTo || global;

    for (var part; parts.length && (part = parts.shift());) {
      if (!parts.length && opt_object !== undefined) {
        // last part and we have an object; use it
        cur[part] = opt_object;
      } else if (part in cur) {
        cur = cur[part];
      } else {
        cur = cur[part] = {};
      }
    }
    return cur;
  };

  var didLoadModules = false;
  var moduleDependencies = {};
  var moduleStylesheets = {};

  function addModuleDependency(moduleName, dependentModuleName) {
    if (!moduleDependencies[moduleName])
      moduleDependencies[moduleName] = [];

    var dependentModules = moduleDependencies[moduleName];
    var found = false;
    for (var i = 0; i < dependentModules.length; i++)
      if (dependentModules[i] == dependentModuleName)
        found = true;
      if (!found)
        dependentModules.push(dependentModuleName);
  }

  function addModuleStylesheet(moduleName, stylesheetName) {
    if (!moduleStylesheets[moduleName])
      moduleStylesheets[moduleName] = [];

    var stylesheets = moduleStylesheets[moduleName];
    var found = false;
    for (var i = 0; i < stylesheets.length; i++)
      if (stylesheets[i] == stylesheetName)
        found = true;
      if (!found)
        stylesheets.push(stylesheetName);
  }

  function ensureDepsLoaded() {
    if (didLoadModules)
      return;
    didLoadModules = true;

    var req = new XMLHttpRequest();
    var src = moduleBasePath + '/' + 'deps.js';
    req.open('GET', src, false);
    req.send(null);
    if (req.status != 200)
      throw new Error('Could not find ' + deps +
                      '. Run calcdeps.py and try again.');

    base.addModuleStylesheet = addModuleStylesheet;
    base.addModuleDependency = addModuleDependency;
    try {
      // By construction, the deps file should call addModuleDependency.
      eval(req.responseText);
    } catch (e) {
      throw new Error('When loading deps, got ' + e.stack ? e.stack : e);
    }
    delete base.addModuleDependency;
    delete base.addModuleStylesheet;
  }

  var moduleLoadStatus = {};
  function require(dependentModuleName, opt_indentLevel) {
    var indentLevel = opt_indentLevel || 0;

    if (window.FLATTENED) {
      if (!window.FLATTENED[dependentModuleName])
        throw new Error('Somehow, module ' + dependentModuleName +
                        ' didn\'t get flattened!');
      return;
    }
    ensureDepsLoaded();

    mLog('require(' + dependentModuleName + ')', indentLevel);

    if (moduleLoadStatus[dependentModuleName] == 'APPENDED')
      return;
    if (moduleLoadStatus[dependentModuleName] == 'RESOLVING')
      throw new Error('Circular dependency betwen modules. Cannot continue!');
    moduleLoadStatus[dependentModuleName] = 'RESOLVING';

    // Load the module stylesheet first.
    var stylesheets = moduleStylesheets[dependentModuleName] || [];
    for (var i = 0; i < stylesheets.length; i++)
      requireStylesheet(stylesheets[i]);

    // Load the module's dependent scripts after.
    var dependentModules =
        moduleDependencies[dependentModuleName] || [];
    for (var i = 0; i < dependentModules.length; i++)
      require(dependentModules[i], indentLevel + 1);

    mLog('load(' + dependentModuleName + ')', indentLevel);
    // Load the module itself.
    var localPath = dependentModuleName.replace(/\./g, '/') + '.js';
    var src = moduleBasePath + '/' + localPath;
    var text = '<script type="text/javascript" src="' + src +
        '"></' + 'script>';
    base.doc.write(text);
    moduleLoadStatus[dependentModuleName] = 'APPENDED';
  }

  var stylesheetLoadStatus = {};
  function requireStylesheet(dependentStylesheetName) {
    if (window.FLATTENED)
      return;

    if (stylesheetLoadStatus[dependentStylesheetName])
      return;
    stylesheetLoadStatus[dependentStylesheetName] = true;
    var localPath = dependentStylesheetName.replace(/\./g, '/') + '.css';
    var stylesheetPath = moduleBasePath + '/' + localPath;

    var linkEl = document.createElement('link');
    linkEl.setAttribute('rel', 'stylesheet');
    linkEl.setAttribute('href', stylesheetPath);
    base.doc.head.appendChild(linkEl);
  }

  function exportTo(namespace, fn) {
    var obj = exportPath(namespace);
    try {
      var exports = fn();
    } catch (e) {
      console.log('While running exports for ', name, ':');
      console.log(e.stack || e);
      return;
    }

    for (var propertyName in exports) {
      // Maybe we should check the prototype chain here? The current usage
      // pattern is always using an object literal so we only care about own
      // properties.
      var propertyDescriptor = Object.getOwnPropertyDescriptor(exports,
                                                               propertyName);
      if (propertyDescriptor) {
        Object.defineProperty(obj, propertyName, propertyDescriptor);
        mLog('  +' + propertyName);
      }
    }
  };

  /**
   * Fires a property change event on the target.
   * @param {EventTarget} target The target to dispatch the event on.
   * @param {string} propertyName The name of the property that changed.
   * @param {*} newValue The new value for the property.
   * @param {*} oldValue The old value for the property.
   */
  function dispatchPropertyChange(target, propertyName, newValue, oldValue) {
    var e = new base.Event(propertyName + 'Change');
    e.propertyName = propertyName;
    e.newValue = newValue;
    e.oldValue = oldValue;
    target.dispatchEvent(e);
  }

  /**
   * Converts a camelCase javascript property name to a hyphenated-lower-case
   * attribute name.
   * @param {string} jsName The javascript camelCase property name.
   * @return {string} The equivalent hyphenated-lower-case attribute name.
   */
  function getAttributeName(jsName) {
    return jsName.replace(/([A-Z])/g, '-$1').toLowerCase();
  }

  /**
   * The kind of property to define in {@code defineProperty}.
   * @enum {number}
   * @const
   */
  var PropertyKind = {
    /**
     * Plain old JS property where the backing data is stored as a 'private'
     * field on the object.
     */
    JS: 'js',

    /**
     * The property backing data is stored as an attribute on an element.
     */
    ATTR: 'attr',

    /**
     * The property backing data is stored as an attribute on an element. If the
     * element has the attribute then the value is true.
     */
    BOOL_ATTR: 'boolAttr'
  };

  /**
   * Helper function for defineProperty that returns the getter to use for the
   * property.
   * @param {string} name The name of the property.
   * @param {base.PropertyKind} kind The kind of the property.
   * @return {function():*} The getter for the property.
   */
  function getGetter(name, kind) {
    switch (kind) {
      case PropertyKind.JS:
        var privateName = name + '_';
        return function() {
          return this[privateName];
        };
      case PropertyKind.ATTR:
        var attributeName = getAttributeName(name);
        return function() {
          return this.getAttribute(attributeName);
        };
      case PropertyKind.BOOL_ATTR:
        var attributeName = getAttributeName(name);
        return function() {
          return this.hasAttribute(attributeName);
        };
    }
  }

  /**
   * Helper function for defineProperty that returns the setter of the right
   * kind.
   * @param {string} name The name of the property we are defining the setter
   *     for.
   * @param {base.PropertyKind} kind The kind of property we are getting the
   *     setter for.
   * @param {function(*):void} opt_setHook A function to run after the property
   *     is set, but before the propertyChange event is fired.
   * @return {function(*):void} The function to use as a setter.
   */
  function getSetter(name, kind, opt_setHook) {
    switch (kind) {
      case PropertyKind.JS:
        var privateName = name + '_';
        return function(value) {
          var oldValue = this[privateName];
          if (value !== oldValue) {
            this[privateName] = value;
            if (opt_setHook)
              opt_setHook.call(this, value, oldValue);
            dispatchPropertyChange(this, name, value, oldValue);
          }
        };

      case PropertyKind.ATTR:
        var attributeName = getAttributeName(name);
        return function(value) {
          var oldValue = this[attributeName];
          if (value !== oldValue) {
            if (value == undefined)
              this.removeAttribute(attributeName);
            else
              this.setAttribute(attributeName, value);
            if (opt_setHook)
              opt_setHook.call(this, value, oldValue);
            dispatchPropertyChange(this, name, value, oldValue);
          }
        };

      case PropertyKind.BOOL_ATTR:
        var attributeName = getAttributeName(name);
        return function(value) {
          var oldValue = this[attributeName];
          if (value !== oldValue) {
            if (value)
              this.setAttribute(attributeName, name);
            else
              this.removeAttribute(attributeName);
            if (opt_setHook)
              opt_setHook.call(this, value, oldValue);
            dispatchPropertyChange(this, name, value, oldValue);
          }
        };
    }
  }

  /**
   * Defines a property on an object. When the setter changes the value a
   * property change event with the type {@code name + 'Change'} is fired.
   * @param {!Object} obj The object to define the property for.
   * @param {string} name The name of the property.
   * @param {base.PropertyKind=} opt_kind What kind of underlying storage to
   * use.
   * @param {function(*):void} opt_setHook A function to run after the
   *     property is set, but before the propertyChange event is fired.
   */
  function defineProperty(obj, name, opt_kind, opt_setHook) {
    if (typeof obj == 'function')
      obj = obj.prototype;

    var kind = opt_kind || PropertyKind.JS;

    if (!obj.__lookupGetter__(name))
      obj.__defineGetter__(name, getGetter(name, kind));

    if (!obj.__lookupSetter__(name))
      obj.__defineSetter__(name, getSetter(name, kind, opt_setHook));
  }

  /**
   * Counter for use with createUid
   */
  var uidCounter = 1;

  /**
   * @return {number} A new unique ID.
   */
  function createUid() {
    return uidCounter++;
  }

  /**
   * Returns a unique ID for the item. This mutates the item so it needs to be
   * an object
   * @param {!Object} item The item to get the unique ID for.
   * @return {number} The unique ID for the item.
   */
  function getUid(item) {
    if (item.hasOwnProperty('uid'))
      return item.uid;
    return item.uid = createUid();
  }

  /**
   * Dispatches a simple event on an event target.
   * @param {!EventTarget} target The event target to dispatch the event on.
   * @param {string} type The type of the event.
   * @param {boolean=} opt_bubbles Whether the event bubbles or not.
   * @param {boolean=} opt_cancelable Whether the default action of the event
   *     can be prevented.
   * @return {boolean} If any of the listeners called {@code preventDefault}
   *     during the dispatch this will return false.
   */
  function dispatchSimpleEvent(target, type, opt_bubbles, opt_cancelable) {
    var e = new base.Event(type, opt_bubbles, opt_cancelable);
    return target.dispatchEvent(e);
  }

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

  /**
   * Creates a new event to be used with base.EventTarget or DOM EventTarget
   * objects.
   * @param {string} type The name of the event.
   * @param {boolean=} opt_bubbles Whether the event bubbles.
   *     Default is false.
   * @param {boolean=} opt_preventable Whether the default action of the event
   *     can be prevented.
   * @constructor
   * @extends {Event}
   */
  function Event(type, opt_bubbles, opt_preventable) {
    var e = base.doc.createEvent('Event');
    e.initEvent(type, !!opt_bubbles, !!opt_preventable);
    e.__proto__ = global.Event.prototype;
    return e;
  };

  /**
   * Initialization which must be deferred until run-time.
   */
  function initialize() {
    // If 'document' isn't defined, then we must be being pre-compiled,
    // so set a trap so that we're initialized on first access at run-time.
    if (!global.document) {
      var originalCr = cr;

      Object.defineProperty(global, 'cr', {
        get: function() {
          Object.defineProperty(global, 'cr', {value: originalCr});
          originalBase.initialize();
          return originalCr;
        },
        configurable: true
      });

      return;
    }

    Event.prototype = {__proto__: global.Event.prototype};

    base.doc = document;

    base.isMac = /Mac/.test(navigator.platform);
    base.isWindows = /Win/.test(navigator.platform);
    base.isChromeOS = /CrOS/.test(navigator.userAgent);
    base.isLinux = /Linux/.test(navigator.userAgent);
    base.isGTK = /GTK/.test(chrome.toolkit);
    base.isViews = /views/.test(chrome.toolkit);

    setModuleBasePath('/src');
  }

  return {
    set moduleBasePath(path) {
      setModuleBasePath(path);
    },

    get moduleBasePath() {
      return moduleBasePath;
    },

    require: require,
    requireStylesheet: requireStylesheet,
    exportTo: exportTo,

    addSingletonGetter: addSingletonGetter,
    createUid: createUid,
    defineProperty: defineProperty,
    dispatchPropertyChange: dispatchPropertyChange,
    dispatchSimpleEvent: dispatchSimpleEvent,
    Event: Event,
    getUid: getUid,
    initialize: initialize,
    PropertyKind: PropertyKind
  };
})();


/**
 * TODO(kgr): Move this to another file which is to be loaded last.
 * This will be done as part of future work to make this code pre-compilable.
 */
base.initialize();
