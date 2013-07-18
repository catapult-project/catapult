// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview A base class for scrollbar-like controls.
 */
base.require('ui');
base.require('base.properties');
base.require('ui.mouse_tracker');

base.requireStylesheet('ui.value_bar');

base.exportTo('ui', function() {

  /**
   * @constructor
   */
  var ValueBar = ui.define('value-bar');

  ValueBar.prototype = {
    __proto__: HTMLDivElement.prototype,

    decorate: function() {
      this.className = 'value-bar';
      this.lowestValueControl_ = this.createLowestValueControl_();
      this.valueRangeControl_ = this.createValueRangeControl_();
      this.highestValueControl_ = this.createHighestValueControl_();
      this.valueSliderControl_ =
          this.createValueSlider_(this.valueRangeControl_);

      this.vertical = true;
      this.exponentBase_ = 1.0;
      this.lowestValue = 0.1;
      this.highestValue = 2.0;
      this.value = 0.5;
    },

    get lowestValue() {
      return this.lowestValue_;
    },

    set lowestValue(newValue) {
      base.setPropertyAndDispatchChange(this, 'lowestValue', newValue);
    },

    get value() {
      return this.value_;
    },

    set value(newValue) {
      if (newValue === this.value)
        return;
      newValue = this.limitValue_(newValue);
      base.setPropertyAndDispatchChange(this, 'value', newValue);
    },

    // A value that changes when you mouseover slider.
    get previewValue() {
      return this.previewValue_;
    },

    set previewValue(newValue) {
      if (newValue === this.previewValue_)
        return;
      newValue = this.limitValue_(newValue);
      base.setPropertyAndDispatchChange(this, 'previewValue', newValue);
    },

    get highestValue() {
      return this.highestValue_;
    },

    set highestValue(newValue) {
      base.setPropertyAndDispatchChange(this, 'highestValue', newValue);
    },

    get vertical() {
      return this.vertical_;
    },

    set vertical(newValue) {
      this.vertical_ = !!newValue;
      delete this.rangeControlOffset_;
      delete this.rangeControlPixelRange_;
      delete this.valueSliderCenterOffset_;
      this.setAttribute('orient', this.vertical_ ? 'vertical' : 'horizontal');
      base.setPropertyAndDispatchChange(this, 'value', this.value);
    },

    get exponentBase() {
      return this.exponentBase_;
    },

    // Controls the amount of non-linearity in the value bar.
    // Higher bases make changes at low value value slower
    // and changes at high values faster.
    set exponentBase(newValue) {
      this.exponentBase_ = newValue;
    },

    // Override to change content.
    updateLowestValueElement: function(element) {
      element.removeAttribute('style');
      var str = event.newValue.toFixed(1) + '';
      element.textContent = str.substr(0, 3);
    },

    updateHighestValueElement: function(element) {
      element.removeAttribute('style');
      var str = event.newValue.toFixed(1) + '';
      element.textContent = str.substr(0, 3);
    },

    get rangeControlOffset() {
      if (!this.rangeControlOffset_) {
        var rect = this.valueRangeControl_.getBoundingClientRect();
        this.rangeControlOffset_ = this.vertical_ ? rect.top : rect.left;
      }
      return this.rangeControlOffset_;
    },

    get valueSlideCenterOffset() {
      var offsetDirection = this.vertical_ ? 'offsetTop' : 'offsetLeft';
      return this.valueSliderCenter_[offsetDirection] + 1;
    },

    get rangeControlPixelRange() {
      if (!this.rangeControlPixelRange_ || this.rangeControlPixelRange_ < 1) {
        var rangeRect = this.valueRangeControl_.getBoundingClientRect();
        this.rangeControlPixelRange_ =
            this.vertical_ ? rangeRect.height - 1 : rangeRect.width - 1;
      }
      return this.rangeControlPixelRange_;
    },

    // The value <--> pixel conversion formulas are all normalized to the
    // range 0-1 to avoid overflow surprises. Three layers of normalization
    // include:
    // 1. pixel range of the valuebar
    // 2. exponent/log of the normalized ranges
    // 3. value range

    // offset zero gives 0, offset rangeControlPixelRange_ gives 1,
    // exponential in between.
    fractionalValue_: function(offset) {
      if (!this.rangeControlPixelRange)
        return 0;
      console.assert(offset >= 0);
      // min offset is zero, so this ratio is (offset - min) / (max - min)
      var fractionOfRange = offset / this.rangeControlPixelRange_;
      if (fractionOfRange > 1)
        fractionOfRange = 1.0;
      if (this.exponentBase === 1)
        return fractionOfRange;
      // The - 1 terms are Math.pow(this.exponentBase_, 0) for the minimum
      // pixel range of zero.
      var numerator = Math.pow(this.exponentBase_, fractionOfRange) - 1;
      return numerator / (this.exponentBase_ - 1);
    },

    // fractionalValue zero gives zero, 1.0 gives rangeControlPixelRange_
    pixelByValue_: function(fractionalValue) {
      console.assert(fractionalValue >= 0 && fractionalValue <= 1);
      if (this.exponentBase_ === 1)
        return this.rangeControlPixelRange * fractionalValue;

      // fractionalValue *(this.exponentBase_^1 - this.exponentBase_^0) +
      //   this.exponentBase_^0
      var expPixel = fractionalValue * (this.exponentBase_ - 1) + 1;
      var fractionalPixel = Math.log(expPixel) / Math.log(this.exponentBase_);
      // (max - min) * fractionalPixel + min for min == 0
      return this.rangeControlPixelRange * fractionalPixel;
    },

    limitValue_: function(newValue) {
      var limitedValue = newValue;
      if (newValue < this.lowestValue)
        limitedValue = this.lowestValue;
      if (newValue > this.highestValue)
        limitedValue = this.highestValue;
      return limitedValue;
    },

    eventToPixelOffset_: function(event) {
      var coord = this.vertical_ ? 'y' : 'x';
      var pixelOffset = event[coord] - this.rangeControlOffset;
      return Math.max(pixelOffset, 1);
    },

    convertPixelOffsetToValue_: function(offset) {
      var rangeInValue = this.highestValue - this.lowestValue;
      return this.fractionalValue_(offset) * (rangeInValue) + this.lowestValue;
    },

    convertValueToPixelOffset: function(value) {
      if (!this.highestValue)
        return 0;
      var rangeInValue = this.highestValue - this.lowestValue;
      var valueInPx =
          this.pixelByValue_((value - this.lowestValue) / rangeInValue);
      return valueInPx;
    },

    setValueOnRangeClick_: function(event) {
      var pixelOffset = this.eventToPixelOffset_(event);
      this.value = this.convertPixelOffsetToValue_(pixelOffset);
    },

    setPreviewValueByEvent_: function(event) {
      var pixelOffset = this.eventToPixelOffset_(event);
      if (event.currentTarget.classList.contains('lowest-value-control'))
        pixelOffset = 0; // There is a 4 pixel error on the bottom of the range.
      this.previewValue = this.convertPixelOffsetToValue_(pixelOffset);
    },
    /**
      @param {Event} event: mouse event relative to slider control
    */
    slideStart_: function(event) {
      this.slideStart_ = event;
    },
    /**
      @param {Event} event: mouse event relative to slider control
    */
    slideValue_: function(event) {
      var pixelOffset = this.eventToPixelOffset_(event);
      this.value =
          this.convertPixelOffsetToValue_(pixelOffset);
    },

    slideEnd_: function(event) {
      this.preview = this.value;
    },

    onValueChange_: function(valueKey) {
      var pixelOffset = this.convertValueToPixelOffset(this[valueKey]);
      pixelOffset = pixelOffset - this.valueSlideCenterOffset;
      if (this.vertical_) {
        this.valueSliderControl_.style.left = 0;
        this.valueSliderControl_.style.top = pixelOffset + 'px';
      } else {
        this.valueSliderControl_.style.left = pixelOffset + 'px';
        this.valueSliderControl_.style.top = 0;
      }
    },

    createValueControl_: function(className) {
      return ui.createDiv({
        className: className + ' value-control',
        parent: this
      });
    },

    createLowestValueControl_: function() {
      var lowestValueControl = this.createValueControl_('lowest-value-control');

      lowestValueControl.addEventListener('click', function() {
        this.value = this.lowestValue;
        base.dispatchSimpleEvent(this, 'lowestValueClick');
      }.bind(this));
      lowestValueControl.addEventListener('mouseover',
          this.setPreviewValueByEvent_.bind(this));

      // Interior element to control the whitespace around the button text
      var lowestValueControlContent =
          ui.createSpan({className: 'lowest-value-control-content'});
      lowestValueControl.appendChild(lowestValueControlContent);

      this.addEventListener('lowestValueChange', function(event) {
        this.updateLowestValueElement(lowestValueControlContent);
      }.bind(this));

      return lowestValueControl;
    },

    createValueRangeControl_: function() {
      var valueRangeControl = this.createValueControl_('value-range-control');
      // As the user moves over our range control, preview the result.
      valueRangeControl.addEventListener('mousemove',
          this.setPreviewValueByEvent_.bind(this));
      // Accept the current value.
      valueRangeControl.addEventListener('click',
          this.setValueOnRangeClick_.bind(this));
      this.addEventListener('valueChange',
          this.onValueChange_.bind(this, 'value'), true);
      return valueRangeControl;
    },

    createHighestValueControl_: function() {
      var highestValueControl =
          this.createValueControl_('highest-value-control');
      highestValueControl.addEventListener('click', function() {
        this.value = this.highestValue;
        base.dispatchSimpleEvent(this, 'highestValueClick');
      }.bind(this));
      var highestValueControlContent =
          ui.createSpan({className: 'highest-value-control-content'});
      highestValueControl.appendChild(highestValueControlContent);
      this.addEventListener('highestValueChange', function(event) {
        this.updateHighestValueElement(highestValueControlContent);
      }.bind(this));
      return highestValueControl;
    },

    createValueSlider_: function(rangeControl) {
      var valueSlider = ui.createDiv({
        className: 'value-slider',
        parent: rangeControl
      });
      ui.createDiv({
        className: 'value-slider-top',
        parent: valueSlider
      });
      this.valueSliderCenter_ = ui.createDiv({
        className: 'value-slider-bottom',
        parent: valueSlider
      });

      this.mouseTracker = new ui.MouseTracker(valueSlider);
      valueSlider.addEventListener('mouse-tracker-start',
          this.slideStart_.bind(this));
      valueSlider.addEventListener('mouse-tracker-move',
          this.slideValue_.bind(this));
      valueSlider.addEventListener('mouse-tracker-end',
          this.slideEnd_.bind(this));
      return valueSlider;
    },

  };

  return {
    ValueBar: ValueBar
  };
});
