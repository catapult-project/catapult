// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * @fileoverview Merge matches from contained RegExpSelectors
 * to control TrackSelector visiblility.
 */
base.requireStylesheet('tracing.tracks.track_selector');
base.require('ui');
base.require('ui.regexp_selector');
base.exportTo('tracing.tracks', function() {

  /**
   * @constructor
   */
  var TrackSelector = ui.define('div');

  TrackSelector.defaultModel = [
    {regexpText: 'CrBrowserMain|Gpu|Renderer', isOn: false},
    {regexpText: null, isOn: false}
  ];

  TrackSelector.storageKey = 'traceViewer.TrackSelector';

  TrackSelector.prototype = {
    __proto__: HTMLDivElement.prototype,

    decorate: function() {
      this.className = 'track-selector';

      this.showHiddenTracksButton_ = this.createshowHiddenTracksButton_();
      this.appendChild(this.showHiddenTracksButton_);

      this.loadModel_();

      this.createRegExpSelectors_();
    },

    loadModel_: function() {
      var settings = new base.Settings();
      var modelJSON = settings.get('TrackSelector');
      if (modelJSON)
        this.trackSelectorModel = this.createModelFromJSON_(modelJSON);

      if (this.trackSelectorModel)
        return;

      // The stored model did not work for us.
      this.trackSelectorModel = TrackSelector.defaultModel;
      this.saveModel_();
    },

    createModelFromJSON_: function(modelJSON) {
      var savedModel;
      try {
        var fromJSON = JSON.parse(modelJSON);
        // validate input
        if (fromJSON instanceof Array) {
          savedModel = [];
          fromJSON.forEach(function(item) {
            if (!item.regexpText) // skip blanks
              return;
            savedModel.push({
              regexpText: item.regexpText + '',
              isOn: !!item.isOn
            });
          });
        }
      } catch (exc) {
        var from = 'TrackSelector.createModelFromJSON_';
        console.warn(from + ' falling back to default because: ' + exc);
      }
      return savedModel;
    },

    saveModel_: function() {
      var modelJSON = JSON.stringify(this.trackSelectorModel);
      var settings = new base.Settings();

      settings.set('TrackSelector', modelJSON);
    },

    updateModelFromElements_: function() {
      this.selectors_.forEach(function(selector, index) {
        this.trackSelectorModel[index] = {
          regexpText: selector.regexp.source,
          isOn: selector.isOn
        };
      }.bind(this));
      this.saveModel_();
    },

    connect: function() {
      this.timelineView_ = this.findAncestorByClass_('timeline-view');
      if (!this.timelineView_)
        return;  // Our parent is not in the DOM, maybe test-code.

      this.showHiddenTracksButton_.addEventListener(
          'click', this.onShowHiddenTracks_.bind(this)
      );

      this.timelineView_.addEventListener(
          'isOnChange', this.onTrackButtonIsOnChange_.bind(this)
      );

      this.timelineView_.addEventListener(
          'modelChange', this.onTrackModelChange_.bind(this)
      );

      this.addEventListener(
          'isOnChange', this.onRegExpSelected_.bind(this)
      );

      this.addEventListener(
          'regexpChange', this.updateModelFromElements_.bind(this)
      );

      this.addEventListener(
          'trackSelectorModelChange', this.onSelectorsModelChange_.bind(this)
      );
    },

    findAncestorByClass_: function(className) {
      var element = this;
      while (element = element.parentElement) {
        if (element.classList.contains(className))
          return element;
      }
    },

    onTrackModelChange_: function() {
      var trackItems = [];
      var trackButtons =
          this.timelineView_.querySelectorAll('.track-button');
      for (var i = 0; i < trackButtons.length; i++) {
        var track = trackButtons[i].parentElement;
        var titles = track.querySelectorAll('.canvas-based-track-title');
        for (var iTitle = 0; iTitle < titles.length; iTitle++) {
          var title = titles[iTitle];
          if (title.textContent.trim().length) {
            trackItems.push({text: title.textContent, data: trackButtons[i]});
          }
        }
      }
      this.selectors_.forEach(function(selector) {
        selector.clearItems();
        trackItems.forEach(function(item) {
          selector.addFilterableItem(item.text, item.data);
        });
      });
    },

    createshowHiddenTracksButton_: function() {
      var showHiddenTracksButton_ = document.createElement('button');
      showHiddenTracksButton_.className = 'show-hidden-tracks-button';
      showHiddenTracksButton_.textContent = 'Show Hidden Tracks';
      showHiddenTracksButton_.disabled = true;
      showHiddenTracksButton_.hiddenTracks_ = 0;
      return showHiddenTracksButton_;
    },

    onSelectorsModelChange_: function(event) {
      if (this.selectors_) {
        this.selectors_.forEach(function(selector) {
          this.removeChild(selector);
        }.bind(this));
      }
      this.createRegExpSelectors_();
      this.onTrackModelChange_();
      this.onItemsChange_();
    },

    createRegExpSelectors_: function() {
      this.selectors_ = this.trackSelectorModel.map(
          this.createRegExpSelector_.bind(this));
    },

    createRegExpSelector_: function(selectorModel) {
      var regExpSelector = new ui.RegExpSelector();

      if (selectorModel.regexp) {
        regExpSelector.regexp = new RegExp(selectorModel.regexp);
        regExpSelector.isOn = !!selectorModel.isOn;
      }

      regExpSelector.addEventListener(
          'itemsChange',
          this.onItemsChange_.bind(this)
      );

      this.appendChild(regExpSelector);
      return regExpSelector;
    },

    ensureOneBlank_: function() {
      var aBlank = this.selectors_.some(function(selector) {
        return selector.regexp.source === ui.RegExpSelector.defaultSource;
      });
      if (!aBlank) {
        this.selectors_.push(
            this.createRegExpSelector_({regexp: '', isOn: false})
        );
        this.onTrackModelChange_();
      }
    },

    onItemsChange_: function() {
      var mergedItems;
      this.selectors_.forEach(function(selector) {
        if (selector.isOn) {
          var items = selector.items;
          if (mergedItems)
            mergedItems = this.mergeItems_(mergedItems, items);
          else
            mergedItems = this.convertItems_(items);
        }
      }.bind(this));

      if (mergedItems)
        this.applySelection_(mergedItems);
      else
        this.onShowHiddenTracks_();

      this.ensureOneBlank_();
    },

    mergeItems_: function(mergedItems, items) {
      items.forEach(function(item, index) {
        mergedItems[index].matches =
            mergedItems[index].matches || items[index].matches;
      });
      return mergedItems;
    },

    convertItems_: function(items) {
      return items.map(function(item) {
        return {text: item.text, element: item.data, matches: item.matches};
      });
    },

    applySelection_: function(items) {
      items.forEach(function(item) {
        item.element.isOn = item.matches;
      });
    },

    onShowHiddenTracks_: function(event) {
      var trackButtons = this.timelineView_.querySelectorAll('.track-button');
      for (var i = 0; i < trackButtons.length; i++) {
        trackButtons[i].isOn = true;
      }
      this.selectors_.forEach(function(selector) {
        selector.isOn = false;
      });
    },

    onTrackButtonIsOnChange_: function(event) {
      if (!event.target.classList.contains('track-button'))
        return;

      // track-button isOn controls track visibility
      this.showHiddenTracksButton_.hiddenTracks_ += (event.newValue ? -1 : 1);
      this.showHiddenTracksButton_.disabled =
          (this.showHiddenTracksButton_.hiddenTracks_ === 0);
    },

    onRegExpSelected_: function(event) {
      if (!event.target.parentElement.classList.contains('regexp-selector'))
        return;
      this.updateModelFromElements_();
      this.onItemsChange_();
    }

  };

  // Input, array of {regexp: RegExp, isOn: boolean}
  base.defineProperty(TrackSelector, 'trackSelectorModel',
      base.PropertyKind.JS);

  return {
    TrackSelector: TrackSelector
  };
});
