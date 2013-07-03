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

  // TODO(dsinclair): Remove this when HTML imports land as the templates
  // will be pulled in by the requireTemplate calls.
  var templatesLoaded_ = false;
  function ensureTemplatesLoaded() {
    if (templatesLoaded_ || window.FLATTENED)
      return;
    templatesLoaded_ = true;

    var req = new XMLHttpRequest();
    req.open('GET', '/templates', false);
    req.send(null);

    var elem = document.createElement('div');
    elem.innerHTML = req.responseText;
    while (elem.hasChildNodes())
      document.head.appendChild(elem.removeChild(elem.firstChild));
  }

  var moduleLoadStatus = {};
  var rawScriptLoadStatus = {};
  function require(modules, opt_indentLevel) {
    var indentLevel = opt_indentLevel || 0;
    var dependentModules = modules;
    if (!(modules instanceof Array))
      dependentModules = [modules];

    ensureDepsLoaded();
    ensureTemplatesLoaded();

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
    scriptEl.src = moduleBasePath + '/' + path;
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
    var stylesheetPath = moduleBasePath + '/' + localPath;

    var linkEl = document.createElement('link');
    linkEl.setAttribute('rel', 'stylesheet');
    linkEl.setAttribute('href', stylesheetPath);
    base.doc.head.appendChild(linkEl);
  }

  var templateLoadStatus = {};
  function requireTemplate(template) {
    if (window.FLATTENED)
      return;

    if (templateLoadStatus[template])
      return;
    templateLoadStatus[template] = true;

    var localPath = template.replace(/\./g, '/') + '.html';
    var importPath = moduleBasePath + '/' + localPath;

    var linkEl = document.createElement('link');
    linkEl.setAttribute('rel', 'import');
    linkEl.setAttribute('href', importPath);
    // TODO(dsinclair): Enable when HTML imports are available.
    //base.doc.head.appendChild(linkEl);
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

    initialize: initialize,

    require: require,
    requireStylesheet: requireStylesheet,
    requireRawScript: requireRawScript,
    requireTemplate: requireTemplate,
    exportTo: exportTo
  };
})();

base.initialize();
