"use strict";
/* eslint-disable new-cap, no-new */

var sinon = require("sinon");
var AssertionError = require("chai").AssertionError;
var expect = require("chai").expect;

describe("Calling with new", function () {
    var spy = null;

    beforeEach(function () {
        spy = sinon.spy();
    });

    describe("calledWithNew", function () {
        it("should throw an assertion error if the spy is never called", function () {
            expect(function () {
                spy.should.have.been.calledWithNew;
            }).to.throw(AssertionError);
        });

        it("should throw an assertion error if the spy is called without `new`", function () {
            spy();

            expect(function () {
                spy.should.have.been.calledWithNew;
            }).to.throw(AssertionError);
            expect(function () {
                spy.getCall(0).should.have.been.calledWithNew;
            }).to.throw(AssertionError);
        });

        it("should not throw if the spy is called with `new`", function () {
            new spy();

            expect(function () {
                spy.should.have.been.calledWithNew;
            }).to.not.throw();
            expect(function () {
                spy.getCall(0).should.have.been.calledWithNew;
            }).to.not.throw();
        });

        it("should not throw if the spy is called with `new` and also without `new`", function () {
            spy();
            new spy();

            expect(function () {
                spy.should.have.been.calledWithNew;
            }).to.not.throw();
            expect(function () {
                spy.getCall(1).should.have.been.calledWithNew;
            }).to.not.throw();
        });
    });

    describe("always calledWithNew", function () {
        it("should throw an assertion error if the spy is never called", function () {
            expect(function () {
                spy.should.always.have.been.calledWithNew;
            }).to.throw(AssertionError);
            expect(function () {
                spy.should.have.always.been.calledWithNew;
            }).to.throw(AssertionError);
            expect(function () {
                spy.should.have.been.always.calledWithNew;
            }).to.throw(AssertionError);
        });

        it("should throw an assertion error if the spy is called without `new`", function () {
            spy();

            expect(function () {
                spy.should.always.have.been.calledWithNew;
            }).to.throw(AssertionError);
            expect(function () {
                spy.should.have.always.been.calledWithNew;
            }).to.throw(AssertionError);
            expect(function () {
                spy.should.have.been.always.calledWithNew;
            }).to.throw(AssertionError);
        });

        it("should not throw if the spy is called with `new`", function () {
            new spy();

            expect(function () {
                spy.should.always.have.been.calledWithNew;
            }).to.not.throw();
            expect(function () {
                spy.should.have.always.been.calledWithNew;
            }).to.not.throw();
            expect(function () {
                spy.should.have.been.always.calledWithNew;
            }).to.not.throw();
        });

        it("should throw an assertion error if the spy is called with `new` and also without `new`", function () {
            spy();
            new spy();

            expect(function () {
                spy.should.always.have.been.calledWithNew;
            }).to.throw(AssertionError);
            expect(function () {
                spy.should.have.always.been.calledWithNew;
            }).to.throw(AssertionError);
            expect(function () {
                spy.should.have.been.always.calledWithNew;
            }).to.throw(AssertionError);
        });
    });
});
