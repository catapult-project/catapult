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
this.tvcm = (function() {
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
  var resourceFileNames = {};

  function setResourceFileName(moduleName, relativeFileName) {
    if (resourceFileNames[moduleName] !== undefined)
      throw new Error('Cannot set file name twice!');
    resourceFileNames[moduleName] = relativeFileName;
  }

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

  function addModuleRawScriptDependency(moduleName, rawScriptFilename) {
    if (!moduleRawScripts[moduleName])
      moduleRawScripts[moduleName] = [];

    var dependentRawScripts = moduleRawScripts[moduleName];
    var found = false;
    for (var i = 0; i < moduleRawScripts.length; i++)
      if (dependentRawScripts[i] == rawScriptFilename)
        found = true;
      if (!found)
        dependentRawScripts.push(rawScriptFilename);
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
    var src = '/tvcm/deps.js';
    req.open('GET', src, false);
    req.send(null);
    if (req.status != 200) {
      var serverSideException = JSON.parse(req.responseText);
      var msg = 'You have a module problem: ' +
          serverSideException.message;
      showPanic(serverSideException.message,
                serverSideException.details);
      throw new Error(msg);
    }

    tvcm.setResourceFileName = setResourceFileName;
    tvcm.addModuleDependency = addModuleDependency;
    tvcm.addModuleRawScriptDependency = addModuleRawScriptDependency;
    tvcm.addModuleStylesheet = addModuleStylesheet;
    try {
      // By construction, the deps should call addModuleDependency.
      eval(req.responseText);
    } catch (e) {
      throw new Error('When loading deps, got ' +
                      e.stack ? e.stack : e.message);
    }
    delete tvcm.setResourceFileName;
    delete tvcm.addModuleStylesheet;
    delete tvcm.addModuleRawScriptDependency;
    delete tvcm.addModuleDependency;
  }

  var panicElement = undefined;
  var rawPanicMessages = [];
  function showPanicElementIfNeeded() {
    if (panicElement)
      return;

    var panicOverlay = document.createElement('div');
    panicOverlay.style.backgroundColor = 'white';
    panicOverlay.style.border = '3px solid red';
    panicOverlay.style.boxSizing = 'border-box';
    panicOverlay.style.color = 'black';
    panicOverlay.style.display = '-webkit-flex';
    panicOverlay.style.height = '100%';
    panicOverlay.style.left = 0;
    panicOverlay.style.padding = '8px';
    panicOverlay.style.position = 'fixed';
    panicOverlay.style.top = 0;
    panicOverlay.style.webkitFlexDirection = 'column';
    panicOverlay.style.width = '100%';

    panicElement = document.createElement('div');
    panicElement.style.webkitFlex = '1 1 auto';
    panicElement.style.overflow = 'auto';
    panicOverlay.appendChild(panicElement);

    if (!document.body) {
      setTimeout(function() {
        document.body.appendChild(panicOverlay);
      }, 150);
    } else {
      document.body.appendChild(panicOverlay);
    }
  }

  function showPanic(panicTitle, panicDetails) {
    showPanicElementIfNeeded();
    var panicMessageEl = document.createElement('div');
    panicMessageEl.innerHTML =
        '<h2 id="message"></h2>' +
        '<pre id="details"></pre>';
    panicMessageEl.querySelector('#message').textContent = panicTitle;
    panicMessageEl.querySelector('#details').textContent = panicDetails;
    panicElement.appendChild(panicMessageEl);

    rawPanicMessages.push({
      title: panicTitle,
      details: panicDetails
    });
  }

  function hasPanic() {
    return rawPanicMessages.length !== 0;
  }
  function getPanicText() {
    return rawPanicMessages.map(function(msg) {
      return msg.title;
    }).join(', ');
  }

  // TODO(dsinclair): Remove this when HTML imports land as the templates
  // will be pulled in by the requireTemplate calls.
  var templatesLoaded_ = false;
  function ensureTemplatesLoaded() {
    if (templatesLoaded_ || window.FLATTENED)
      return;
    templatesLoaded_ = true;

    var req = new XMLHttpRequest();
    req.open('GET', '/tvcm/all_templates.html', false);
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
    if (dependentModuleName == 'tvcm')
      return;

    if (window.FLATTENED) {
      if (!window.FLATTENED[dependentModuleName]) {
        throw new Error('Somehow, module ' + dependentModuleName +
                        ' didn\'t get stored in the flattened js file! ' +
                        'You have likely found a tvcm bug.');
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

    if (resourceFileNames[dependentModuleName] === undefined)
      throw new Error('Not sure what filename is for ' + dependentModuleName);
    loadScript(resourceFileNames[dependentModuleName]);
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
      var rawScriptFilename = rawScripts[i];
      if (rawScriptLoadStatus[rawScriptFilename])
        continue;

      loadScript(rawScriptFilename);
      mLog('load(' + rawScriptFilename + ')', indentLevel);
      rawScriptLoadStatus[rawScriptFilename] = 'APPENDED';
    }
  }

  function loadScript(path) {
    var scriptEl = document.createElement('script');
    scriptEl.src = '/' + path;
    scriptEl.type = 'text/javascript';
    scriptEl.defer = true;
    scriptEl.async = false;
    tvcm.doc.head.appendChild(scriptEl);
  }

  /**
   * Adds a dependency on a raw javascript file, e.g. a third party
   * library.
   * @param {String} rawScriptFilename The path to the script file, relative to
   * the calling file. rawScriptFilename must be in the data path used by the
   * calling project, typically a third_party directory.
   */
  function requireRawScript(relativeRawScriptPath) {
    if (window.FLATTENED_RAW_SCRIPTS) {
      if (!window.FLATTENED_RAW_SCRIPTS[relativeRawScriptPath]) {
        throw new Error('Somehow, ' + relativeRawScriptPath +
            ' didn\'t get stored in the flattened js file! ' +
            'You have probably found a tvcm bug.');
      }
      return;
    }

    if (rawScriptLoadStatus[relativeRawScriptPath])
      return;
    throw new Error(
        relativeRawScriptPath + ' should already have been loaded.' +
        'You have probably found a tvcm bug.');
  }

  var stylesheetLoadStatus = {};
  function requireStylesheet(dependentStylesheetName) {
    if (window.FLATTENED)
      return;

    if (stylesheetLoadStatus[dependentStylesheetName])
      return;
    stylesheetLoadStatus[dependentStylesheetName] = true;

    var localPath = dependentStylesheetName.replace(/\./g, '/') + '.css';
    var stylesheetPath = '/' + localPath;

    var linkEl = document.createElement('link');
    linkEl.setAttribute('rel', 'stylesheet');
    linkEl.setAttribute('href', stylesheetPath);
    tvcm.doc.head.appendChild(linkEl);
  }

  var templateLoadStatus = {};
  function requireTemplate(template) {
    if (window.FLATTENED)
      return;

    if (templateLoadStatus[template])
      return;
    templateLoadStatus[template] = true;

    var localPath = template.replace(/\./g, '/') + '.html';
    var importPath = localPath;

    var linkEl = document.createElement('link');
    linkEl.setAttribute('rel', 'import');
    linkEl.setAttribute('href', importPath);
    // TODO(dsinclair): Enable when HTML imports are available.
    //tvcm.doc.head.appendChild(linkEl);
  }

  function exportTo(namespace, fn) {
    var obj = exportPath(namespace);
    var exports = fn();

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
      var originalTVCM = tvcm;

      Object.defineProperty(global, 'tvcm', {
        get: function() {
          Object.defineProperty(global, 'tvcm', {value: originalTVCM});
          originalTVCM.initialize();
          return originalTVCM;
        },
        configurable: true
      });

      return;
    }

    tvcm.doc = document;

    tvcm.isMac = /Mac/.test(navigator.platform);
    tvcm.isWindows = /Win/.test(navigator.platform);
    tvcm.isChromeOS = /CrOS/.test(navigator.userAgent);
    tvcm.isLinux = /Linux/.test(navigator.userAgent);
    tvcm.isGTK = /GTK/.test(chrome.toolkit);
    tvcm.isViews = /views/.test(chrome.toolkit);
  }

  return {
    initialize: initialize,

    require: require,
    requireStylesheet: requireStylesheet,
    requireRawScript: requireRawScript,
    requireTemplate: requireTemplate,
    exportTo: exportTo,
    showPanic: showPanic,
    hasPanic: hasPanic,
    getPanicText: getPanicText
  };
})();

tvcm.initialize();
