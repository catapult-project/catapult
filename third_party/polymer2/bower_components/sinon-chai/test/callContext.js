"use strict";

var sinon = require("sinon");
var AssertionError = require("chai").AssertionError;
var expect = require("chai").expect;

describe("Call context", function () {
    var spy = null;
    var target = null;
    var notTheTarget = null;

    beforeEach(function () {
        spy = sinon.spy();
        target = {};
        notTheTarget = {};
    });

    describe("calledOn", function () {
        it("should throw an assertion error if the spy is never called", function () {
            expect(function () {
                spy.should.have.been.calledOn(target);
            }).to.throw(AssertionError);
        });

        it("should throw an assertion error if the spy is called without a context", function () {
            spy();

            expect(function () {
                spy.should.have.been.calledOn(target);
            }).to.throw(AssertionError);
            expect(function () {
                spy.getCall(0).should.have.been.calledOn(target);
            }).to.throw(AssertionError);
        });

        it("should throw an assertion error if the spy is called on the wrong context", function () {
            spy.call(notTheTarget);

            expect(function () {
                spy.should.have.been.calledOn(target);
            }).to.throw(AssertionError);
            expect(function () {
                spy.getCall(0).should.have.been.calledOn(target);
            }).to.throw(AssertionError);
        });

        it("should not throw if the spy is called on the specified context", function () {
            spy.call(target);

            expect(function () {
                spy.should.have.been.calledOn(target);
            }).to.not.throw();
            expect(function () {
                spy.getCall(0).should.have.been.calledOn(target);
            }).to.not.throw();
        });

        it("should not throw if the spy is called on another context and also the specified context", function () {
            spy.call(notTheTarget);
            spy.call(target);

            expect(function () {
                spy.should.have.been.calledOn(target);
            }).to.not.throw();
            expect(function () {
                spy.getCall(1).should.have.been.calledOn(target);
            }).to.not.throw();
        });
    });

    describe("always calledOn", function () {
        it("should throw an assertion error if the spy is never called", function () {
            expect(function () {
                spy.should.always.have.been.calledOn(target);
            }).to.throw(AssertionError);
            expect(function () {
                spy.should.have.always.been.calledOn(target);
            }).to.throw(AssertionError);
            expect(function () {
                spy.should.have.been.always.calledOn(target);
            }).to.throw(AssertionError);
        });

        it("should throw an assertion error if the spy is called without a context", function () {
            spy();

            expect(function () {
                spy.should.always.have.been.calledOn(target);
            }).to.throw(AssertionError);
            expect(function () {
                spy.should.have.always.been.calledOn(target);
            }).to.throw(AssertionError);
            expect(function () {
                spy.should.have.been.always.calledOn(target);
            }).to.throw(AssertionError);
        });

        it("should throw an assertion error if the spy is called on the wrong context", function () {
            spy.call(notTheTarget);

            expect(function () {
                spy.should.always.have.been.calledOn(target);
            }).to.throw(AssertionError);
            expect(function () {
                spy.should.have.always.been.calledOn(target);
            }).to.throw(AssertionError);
            expect(function () {
                spy.should.have.been.always.calledOn(target);
            }).to.throw(AssertionError);
        });

        it("should not throw if the spy is called on the specified context", function () {
            spy.call(target);

            expect(function () {
                spy.should.always.have.been.calledOn(target);
            }).to.not.throw();
            expect(function () {
                spy.should.have.always.been.calledOn(target);
            }).to.not.throw();
            expect(function () {
                spy.should.have.been.always.calledOn(target);
            }).to.not.throw();
        });

        it("should throw an assertion error if the spy is called on another context and also the specified context",
        function () {
            spy.call(notTheTarget);
            spy.call(target);

            expect(function () {
                spy.should.always.have.been.calledOn(target);
            }).to.throw(AssertionError);
            expect(function () {
                spy.should.have.always.been.calledOn(target);
            }).to.throw(AssertionError);
            expect(function () {
                spy.should.have.been.always.calledOn(target);
            }).to.throw(AssertionError);
        });
    });
});
