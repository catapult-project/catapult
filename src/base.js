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
  var moduleRawScripts = {};

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

  function addModuleRawScriptDependency(moduleName, rawScriptName) {
    if (!moduleRawScripts[moduleName])
      moduleRawScripts[moduleName] = [];

    var dependentRawScripts = moduleRawScripts[moduleName];
    var found = false;
    for (var i = 0; i < moduleRawScripts.length; i++)
      if (dependentRawScripts[i] == rawScriptName)
        found = true;
      if (!found)
        dependentRawScripts.push(rawScriptName);
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
    if (window.FLATTENED)
      return;

    if (didLoadModules)
      return;
    didLoadModules = true;

    var req = new XMLHttpRequest();
    var src = '/deps.js';
    req.open('GET', src, false);
    req.send(null);
    if (req.status != 200) {
      var serverSideException = JSON.parse(req.responseText);
      var msg = 'You have a module problem: ' +
          serverSideException.message;
      var baseWarningEl = document.createElement('div');
      baseWarningEl.style.position = 'fixed';
      baseWarningEl.style.border = '3px solid red';
      baseWarningEl.style.color = 'black';
      baseWarningEl.style.padding = '8px';
      baseWarningEl.innerHTML =
          '<h2>Module parsing problem</h2>' +
          '<div id="message"></div>' +
          '<pre id="details"></pre>';
      baseWarningEl.querySelector('#message').textContent =
          serverSideException.message;
      var detailsEl = baseWarningEl.querySelector('#details');
      detailsEl.textContent = serverSideException.details;
      detailsEl.style.maxWidth = '800px';
      detailsEl.style.overflow = 'auto';

      if (!document.body) {
        setTimeout(function() {
          document.body.appendChild(baseWarningEl);
        }, 150);
      } else {
        document.body.appendChild(baseWarningEl);
      }
      throw new Error(msg);
    }

    base.addModuleDependency = addModuleDependency;
    base.addModuleRawScriptDependency = addModuleRawScriptDependency;
    base.addModuleStylesheet = addModuleStylesheet;
    try {
      // By construction, the deps should call addModuleDependency.
      eval(req.responseText);
    } catch (e) {
      throw new Error('When loading deps, got ' +
                      e.stack ? e.stack : e.message);
    }
    delete base.addModuleStylesheet;
    delete base.addModuleRawScriptDependency;
    delete base.addModuleDependency;
  }

  var moduleLoadStatus = {};
  var rawScriptLoadStatus = {};
  function require(modules, opt_indentLevel) {
    var indentLevel = opt_indentLevel || 0;
    var dependentModules = modules;
    if (!(modules instanceof Array))
      dependentModules = [modules];

    ensureDepsLoaded();

    dependentModules.forEach(function(module) {
      requireModule(module, indentLevel);
    });
  }

  var modulesWaiting = [];
  function requireModule(dependentModuleName, indentLevel) {
    if (window.FLATTENED) {
      if (!window.FLATTENED[dependentModuleName]) {
        throw new Error('Somehow, module ' + dependentModuleName +
                        ' didn\'t get stored in the flattened js file! ' +
                        'You may need to rerun ' +
                        'build/generate_about_tracing_contents.py');
      }
      return;
    }

    if (moduleLoadStatus[dependentModuleName] == 'APPENDED')
      return;

    if (moduleLoadStatus[dependentModuleName] == 'RESOLVING')
      return;

    mLog('require(' + dependentModuleName + ')', indentLevel);
    moduleLoadStatus[dependentModuleName] = 'RESOLVING';
    requireDependencies(dependentModuleName, indentLevel);

    loadScript(dependentModuleName.replace(/\./g, '/') + '.js');
    moduleLoadStatus[name] = 'APPENDED';
  }

  function requireDependencies(dependentModuleName, indentLevel) {
    // Load the module's dependent scripts after.
    var dependentModules = moduleDependencies[dependentModuleName] || [];
    require(dependentModules, indentLevel + 1);

    // Load the module stylesheet first.
    var stylesheets = moduleStylesheets[dependentModuleName] || [];
    for (var i = 0; i < stylesheets.length; i++)
      requireStylesheet(stylesheets[i]);

    // Load the module raw scripts next
    var rawScripts = moduleRawScripts[dependentModuleName] || [];
    for (var i = 0; i < rawScripts.length; i++) {
      var rawScriptName = rawScripts[i];
      if (rawScriptLoadStatus[rawScriptName])
        continue;

      loadScript(rawScriptName);
      mLog('load(' + rawScriptName + ')', indentLevel);
      rawScriptLoadStatus[rawScriptName] = 'APPENDED';
    }
  }

  function loadScript(path) {
    var scriptEl = document.createElement('script');
    scriptEl.src = moduleBasePath + '/' + path; // + '?' + new Date().getTime();
    scriptEl.type = 'text/javascript';
    scriptEl.defer = true;
    scriptEl.async = false;
    base.doc.head.appendChild(scriptEl);
  }

  /**
   * Adds a dependency on a raw javascript file, e.g. a third party
   * library.
   * @param {String} rawScriptName The path to the script file, relative to
   * moduleBasePath.
   */
  function requireRawScript(rawScriptPath) {
    if (window.FLATTENED_RAW_SCRIPTS) {
      if (!window.FLATTENED_RAW_SCRIPTS[rawScriptPath]) {
        throw new Error('Somehow, ' + rawScriptPath +
            ' didn\'t get stored in the flattened js file! ' +
            'You may need to rerun build/generate_about_tracing_contents.py');
      }
      return;
    }

    if (rawScriptLoadStatus[rawScriptPath])
      return;
    throw new Error(rawScriptPath + ' should already have been loaded.' +
        ' Did you forget to run build/generate_about_tracing_contents.py?');
  }

  var stylesheetLoadStatus = {};
  function requireStylesheet(dependentStylesheetName) {
    if (window.FLATTENED)
      return;

    if (stylesheetLoadStatus[dependentStylesheetName])
      return;
    stylesheetLoadStatus[dependentStylesheetName] = true;
    var localPath = dependentStylesheetName.replace(/\./g, '/') + '.css';
    var stylesheetPath = moduleBasePath + '/' + localPath + '?' +
        (new Date().getTime());

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
      console.log('While running exports for ', namespace, ':');
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
  function dispatchPropertyChange(target, propertyName, newValue, oldValue,
                                  opt_bubbles, opt_cancelable) {
    var e = new base.Event(propertyName + 'Change',
        opt_bubbles, opt_cancelable);
    e.propertyName = propertyName;
    e.newValue = newValue;
    e.oldValue = oldValue;

    var error;
    e.throwError = function(err) {  // workaround CR 239648
      error = err;
    }

    target.dispatchEvent(e);
    if (error)
      throw error;
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

  /* Creates a private name unlikely to collide with object properties names
   * @param {string} name The defineProperty name
   * @return {string} an obfuscated name
   */
  function getPrivateName(name) {
    return name + '_base_';
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
        var privateName = getPrivateName(name);
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
   * @param {function(*):void=} opt_setHook A function to run after the property
   *     is set, but before the propertyChange event is fired.
   * @param {boolean=} opt_bubbles Whether the event bubbles or not.
   * @param {boolean=} opt_cancelable Whether the default action of the event
   *     can be prevented.
   * @return {function(*):void} The function to use as a setter.
   */
  function getSetter(name, kind, opt_setHook, opt_bubbles, opt_cancelable) {
    switch (kind) {
      case PropertyKind.JS:
        var privateName = getPrivateName(name);
        return function(value) {
          var oldValue = this[privateName];
          if (value !== oldValue) {
            this[privateName] = value;
            if (opt_setHook)
              opt_setHook.call(this, value, oldValue);
            dispatchPropertyChange(this, name, value, oldValue,
                opt_bubbles, opt_cancelable);
          }
        };

      case PropertyKind.ATTR:
        var attributeName = getAttributeName(name);
        return function(value) {
          var oldValue = this.getAttribute(attributeName);
          if (value !== oldValue) {
            if (value == undefined)
              this.removeAttribute(attributeName);
            else
              this.setAttribute(attributeName, value);
            if (opt_setHook)
              opt_setHook.call(this, value, oldValue);
            dispatchPropertyChange(this, name, value, oldValue,
                opt_bubbles, opt_cancelable);
          }
        };

      case PropertyKind.BOOL_ATTR:
        var attributeName = getAttributeName(name);
        return function(value) {
          var oldValue = (this.getAttribute(attributeName) === name);
          if (value !== oldValue) {
            if (value)
              this.setAttribute(attributeName, name);
            else
              this.removeAttribute(attributeName);
            if (opt_setHook)
              opt_setHook.call(this, value, oldValue);
            dispatchPropertyChange(this, name, value, oldValue,
                opt_bubbles, opt_cancelable);
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
   * @param {function(*):void=} opt_setHook A function to run after the
   *     property is set, but before the propertyChange event is fired.
   * @param {boolean=} opt_bubbles Whether the event bubbles or not.
   * @param {boolean=} opt_cancelable Whether the default action of the event
   *     can be prevented.
   */
  function defineProperty(obj, name, opt_kind, opt_setHook,
                          opt_bubbles, opt_cancelable) {
    if (typeof obj == 'function')
      obj = obj.prototype;

    var kind = opt_kind || PropertyKind.JS;

    if (!obj.__lookupGetter__(name))
      obj.__defineGetter__(name, getGetter(name, kind));

    if (!obj.__lookupSetter__(name))
      obj.__defineSetter__(name, getSetter(name, kind, opt_setHook,
          opt_bubbles, opt_cancelable));
  }

  /**
   * Dispatches a simple event on an event target.
   * @param {!EventTarget} target The event target to dispatch the event on.
   * @param {string} type The type of the event.
   * @param {boolean=} opt_bubbles Whether the event bubbles or not.
   * @param {boolean=} opt_cancelable Whether the default action of the event
   *     can be prevented.
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
      var originalBase = base;

      Object.defineProperty(global, 'base', {
        get: function() {
          Object.defineProperty(global, 'base', {value: originalBase});
          originalBase.initialize();
          return originalBase;
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

  function asArray(arrayish) {
    var values = [];
    for (var i = 0; i < arrayish.length; i++)
      values.push(arrayish[i]);
    return values;
  }

  function concatenateArrays(/*arguments*/) {
    var values = [];
    for (var i = 0; i < arguments.length; i++) {
      if (!(arguments[i] instanceof Array))
        throw new Error('Arguments ' + i + 'is not an array');
      values.push.apply(values, arguments[i]);
    }
    return values;
  }

  function dictionaryKeys(dict) {
    var keys = [];
    for (var key in dict)
      keys.push(key);
    return keys;
  }

  function dictionaryValues(dict) {
    var values = [];
    for (var key in dict)
      values.push(dict[key]);
    return values;
  }

  function iterItems(dict, fn, opt_this) {
    opt_this = opt_this || this;
    for (var key in dict)
      fn.call(opt_this, key, dict[key]);
  }

  function iterObjectFieldsRecursively(object, func) {
    if (!(object instanceof Object))
      return;

    if (object instanceof Array) {
      for (var i = 0; i < object.length; i++) {
        func(object, i, object[i]);
        iterObjectFieldsRecursively(object[i], func);
      }
      return;
    }

    for (var key in object) {
      var value = object[key];

      func(object, key, value);

      iterObjectFieldsRecursively(value, func);
    }
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

  /**
   * Maps types to a given value.
   * @constructor
   */
  function TypeMap() {
    this.types = [];
    this.values = [];
  }
  TypeMap.prototype = {
    __proto__: Object.prototype,

    add: function(type, value) {
      this.types.push(type);
      this.values.push(value);
    },

    get: function(instance) {
      for (var i = 0; i < this.types.length; i++) {
        if (instance instanceof this.types[i])
          return this.values[i];
      }
      return undefined;
    }
  };

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

  return {
    set moduleBasePath(path) {
      setModuleBasePath(path);
    },

    get moduleBasePath() {
      return moduleBasePath;
    },

    require: require,
    requireStylesheet: requireStylesheet,
    requireRawScript: requireRawScript,
    exportTo: exportTo,

    addSingletonGetter: addSingletonGetter,
    defineProperty: defineProperty,
    dispatchPropertyChange: dispatchPropertyChange,
    dispatchSimpleEvent: dispatchSimpleEvent,
    Event: Event,
    initialize: initialize,
    PropertyKind: PropertyKind,
    asArray: asArray,
    concatenateArrays: concatenateArrays,
    dictionaryKeys: dictionaryKeys,
    dictionaryValues: dictionaryValues,
    iterItems: iterItems,
    iterObjectFieldsRecursively: iterObjectFieldsRecursively,
    TypeMap: TypeMap,
    tracedFunction: tracedFunction,
    normalizeException: normalizeException
  };
})();

base.initialize();
