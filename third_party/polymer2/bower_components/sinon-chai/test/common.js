"use strict";

var chai = require("chai");
var sinonChai = require("../lib/sinon-chai");
chai.use(sinonChai);
chai.should();

exports.swallow = function (thrower) {
    try {
        thrower();
    } catch (e) {
      // Intentionally swallow
    }
};
