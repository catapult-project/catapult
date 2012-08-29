// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Provides color scheme related functions.
 */
base.exportTo('tracing', function() {

  // The color palette is split in half, with the upper
  // half of the palette being the "highlighted" verison
  // of the base color. So, color 7's highlighted form is
  // 7 + (palette.length / 2).
  //
  // These bright versions of colors are automatically generated
  // from the base colors.
  //
  // Within the color palette, there are "regular" colors,
  // which can be used for random color selection, and
  // reserved colors, which are used when specific colors
  // need to be used, e.g. where red is desired.
  var paletteBase = [
    {r: 138, g: 113, b: 152},
    {r: 175, g: 112, b: 133},
    {r: 127, g: 135, b: 225},
    {r: 93, g: 81, b: 137},
    {r: 116, g: 143, b: 119},
    {r: 178, g: 214, b: 122},
    {r: 87, g: 109, b: 147},
    {r: 119, g: 155, b: 95},
    {r: 114, g: 180, b: 160},
    {r: 132, g: 85, b: 103},
    {r: 157, g: 210, b: 150},
    {r: 148, g: 94, b: 86},
    {r: 164, g: 108, b: 138},
    {r: 139, g: 191, b: 150},
    {r: 110, g: 99, b: 145},
    {r: 80, g: 129, b: 109},
    {r: 125, g: 140, b: 149},
    {r: 93, g: 124, b: 132},
    {r: 140, g: 85, b: 140},
    {r: 104, g: 163, b: 162},
    {r: 132, g: 141, b: 178},
    {r: 131, g: 105, b: 147},
    {r: 135, g: 183, b: 98},
    {r: 152, g: 134, b: 177},
    {r: 141, g: 188, b: 141},
    {r: 133, g: 160, b: 210},
    {r: 126, g: 186, b: 148},
    {r: 112, g: 198, b: 205},
    {r: 180, g: 122, b: 195},
    {r: 203, g: 144, b: 152},
    // Reserved Entires
    {r: 182, g: 125, b: 143},
    {r: 126, g: 200, b: 148},
    {r: 133, g: 160, b: 210},
    {r: 240, g: 240, b: 240}];

  // Make sure this number tracks the number of reserved entries in the
  // palette.
  var numReservedColorIds = 4;

  function brighten(c) {
    var k;
    if (c.r >= 240 && c.g >= 240 && c.b >= 240)
      k = -0.20;
    else
      k = 0.45;

    return {r: Math.min(255, c.r + Math.floor(c.r * k)),
      g: Math.min(255, c.g + Math.floor(c.g * k)),
      b: Math.min(255, c.b + Math.floor(c.b * k))};
  }
  function colorToString(c) {
    return 'rgb(' + c.r + ',' + c.g + ',' + c.b + ')';
  }

  /**
   * The number of color IDs that getStringColorId can choose from.
   */
  var numRegularColorIds = paletteBase.length - numReservedColorIds;
  var highlightIdBoost = paletteBase.length;

  var palette = paletteBase.concat(paletteBase.map(brighten)).
      map(colorToString);
  /**
   * Computes a simplistic hashcode of the provide name. Used to chose colors
   * for slices.
   * @param {string} name The string to hash.
   */
  function getStringHash(name) {
    var hash = 0;
    for (var i = 0; i < name.length; ++i)
      hash = (hash + 37 * hash + 11 * name.charCodeAt(i)) % 0xFFFFFFFF;
    return hash;
  }

  /**
   * Gets the color palette.
   */
  function getColorPalette() {
    return palette;
  }

  /**
   * @return {Number} The value to add to a color ID to get its highlighted
   * colro ID. E.g. 7 + getPaletteHighlightIdBoost() yields a brightened from
   * of 7's base color.
   */
  function getColorPaletteHighlightIdBoost() {
    return highlightIdBoost;
  }

  /**
   * @param {String} name The color name.
   * @return {Number} The color ID for the given color name.
   */
  function getColorIdByName(name) {
    if (name == 'iowait')
      return numRegularColorIds;
    if (name == 'running')
      return numRegularColorIds + 1;
    if (name == 'runnable')
      return numRegularColorIds + 2;
    if (name == 'sleeping')
      return numRegularColorIds + 3;
    throw new Error('Unrecognized color ') + name;
  }

  // Previously computed string color IDs. They are based on a stable hash, so
  // it is safe to save them throughout the program time.
  var stringColorIdCache = {};

  /**
   * @return {Number} A color ID that is stably associated to the provided via
   * the getStringHash method. The color ID will be chosen from the regular
   * ID space only, e.g. no reserved ID will be used.
   */
  function getStringColorId(string) {
    if (stringColorIdCache[string] === undefined) {
      var hash = getStringHash(string);
      stringColorIdCache[string] = hash % numRegularColorIds;
    }
    return stringColorIdCache[string];
  }

  return {
    getColorPalette: getColorPalette,
    getColorPaletteHighlightIdBoost: getColorPaletteHighlightIdBoost,
    getColorIdByName: getColorIdByName,
    getStringHash: getStringHash,
    getStringColorId: getStringColorId
  };
});
