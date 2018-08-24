"use strict";

var sinon = require("sinon");
var AssertionError = require("chai").AssertionError;
var expect = require("chai").expect;

describe("Returning", function () {
    describe("returned", function () {
        it("should throw an assertion error if the spy does not return the correct value", function () {
            var spy = sinon.spy.create(function () {
                return 1;
            });

            spy();

            expect(function () {
                spy.should.have.returned(2);
            }).to.throw(AssertionError);
            expect(function () {
                spy.getCall(0).should.have.returned(2);
            }).to.throw(AssertionError);
        });

        it("should not throw if the spy returns the correct value", function () {
            var spy = sinon.spy.create(function () {
                return 1;
            });

            spy();

            expect(function () {
                spy.should.have.returned(1);
            }).to.not.throw();
            expect(function () {
                spy.getCall(0).should.have.returned(1);
            }).to.not.throw();
        });

        it("should not throw if the spy returns the correct value amongst others", function () {
            var values = [1, 2, 3];
            var spy = sinon.spy.create(function () {
                return values[spy.callCount - 1];
            });

            spy();
            spy();
            spy();

            expect(function () {
                spy.should.have.returned(1);
            }).to.not.throw();
            expect(function () {
                spy.getCall(0).should.have.returned(1);
            }).to.not.throw();
        });
    });

    describe("always returned", function () {
        it("should throw an assertion error if the spy does not return the correct value", function () {
            var spy = sinon.spy.create(function () {
                return 1;
            });

            spy();

            expect(function () {
                spy.should.always.have.returned(2);
            }).to.throw(AssertionError);
            expect(function () {
                spy.should.have.always.returned(2);
            }).to.throw(AssertionError);
        });

        it("should not throw if the spy returns the correct value", function () {
            var spy = sinon.spy.create(function () {
                return 1;
            });

            spy();

            expect(function () {
                spy.should.have.always.returned(1);
            }).to.not.throw();
            expect(function () {
                spy.should.always.have.returned(1);
            }).to.not.throw();
        });

        it("should throw an assertion error if the spy returns the correct value amongst others", function () {
            var values = [1, 2, 3];
            var spy = sinon.spy.create(function () {
                values[spy.callCount - 1];
            });

            spy();
            spy();
            spy();

            expect(function () {
                spy.should.always.have.returned(1);
            }).to.throw(AssertionError);
            expect(function () {
                spy.should.have.always.returned(1);
            }).to.throw(AssertionError);
        });
    });
});
