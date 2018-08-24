"use strict";

var sinon = require("sinon");
var AssertionError = require("chai").AssertionError;
var expect = require("chai").expect;
var swallow = require("./common").swallow;

describe("Throwing", function () {
    describe("thrown()", function () {
        it("should throw an assertion error if the spy does not throw at all", function () {
            var spy = sinon.spy.create(function () { /* Contents don't matter */ });

            spy();

            expect(function () {
                spy.should.have.thrown();
            }).to.throw(AssertionError);
            expect(function () {
                spy.getCall(0).should.have.thrown();
            }).to.throw(AssertionError);
        });

        it("should not throw if the spy throws", function () {
            var spy = sinon.spy.create(function () {
                throw new Error();
            });

            swallow(spy);

            expect(function () {
                spy.should.have.thrown();
            }).to.not.throw();
            expect(function () {
                spy.getCall(0).should.have.thrown();
            }).to.not.throw();
        });

        it("should not throw if the spy throws once but not the next time", function () {
            var spy = sinon.spy.create(function () {
                if (!(spy.callCount > 1)) {
                    throw new Error();
                }
            });

            swallow(spy);
            swallow(spy);

            expect(function () {
                spy.should.have.thrown();
            }).to.not.throw();
            expect(function () {
                spy.getCall(0).should.have.thrown();
            }).to.not.throw();
        });
    });

    describe("thrown(errorObject)", function () {
        var error = null;

        beforeEach(function () {
            error = new Error("boo!");
        });

        it("should throw an assertion error if the spy does not throw at all", function () {
            var spy = sinon.spy.create(function () { /* Contents don't matter */ });

            spy();

            expect(function () {
                spy.should.have.thrown(error);
            }).to.throw(AssertionError);
            expect(function () {
                spy.getCall(0).should.have.thrown(error);
            }).to.throw(AssertionError);
        });

        it("should throw an assertion error if the spy throws the wrong error", function () {
            var spy = sinon.spy.create(function () {
                return new Error("eek!");
            });

            swallow(spy);

            expect(function () {
                spy.should.have.thrown(error);
            }).to.throw(AssertionError);
            expect(function () {
                spy.getCall(0).should.have.thrown(error);
            }).to.throw(AssertionError);
        });

        it("should not throw if the spy throws", function () {
            var spy = sinon.spy.create(function () {
                throw error;
            });

            swallow(spy);

            expect(function () {
                spy.should.have.thrown(error);
            }).to.not.throw();
            expect(function () {
                spy.getCall(0).should.have.thrown(error);
            }).to.not.throw();
        });

        it("should not throw if the spy throws once but not the next time", function () {
            var spy = sinon.spy.create(function () {
                if (!(spy.callCount > 1)) {
                    throw error;
                }
            });

            swallow(spy);
            swallow(spy);

            expect(function () {
                spy.should.have.thrown(error);
            }).to.not.throw();
            expect(function () {
                spy.getCall(0).should.have.thrown(error);
            }).to.not.throw();
        });
    });

    describe("thrown(errorTypeString)", function () {
        var error = null;

        beforeEach(function () {
            error = new TypeError("boo!");
        });

        it("should throw an assertion error if the spy does not throw at all", function () {
            var spy = sinon.spy.create(function () { /* Contents don't matter */ });

            spy();

            expect(function () {
                spy.should.have.thrown("TypeError");
            }).to.throw(AssertionError);
            expect(function () {
                spy.getCall(0).should.have.thrown("TypeError");
            }).to.throw(AssertionError);
        });

        it("should throw an assertion error if the spy throws the wrong type of error", function () {
            var spy = sinon.spy.create(function () {
                throw new Error("boo!");
            });

            swallow(spy);

            expect(function () {
                spy.should.have.thrown("TypeError");
            }).to.throw(AssertionError);
            expect(function () {
                spy.getCall(0).should.have.thrown("TypeError");
            }).to.throw(AssertionError);
        });

        it("should not throw if the spy throws the correct type of error", function () {
            var spy = sinon.spy.create(function () {
                throw new TypeError("eek!");
            });

            swallow(spy);

            expect(function () {
                spy.should.have.thrown("TypeError");
            }).to.not.throw();
            expect(function () {
                spy.getCall(0).should.have.thrown("TypeError");
            }).to.not.throw();
        });

        it("should not throw if the spy throws once but not the next time", function () {
            var spy = sinon.spy.create(function () {
                if (!(spy.callCount > 1)) {
                    throw error;
                }
            });

            swallow(spy);
            swallow(spy);

            expect(function () {
                spy.should.have.thrown("TypeError");
            }).to.not.throw();
            expect(function () {
                spy.getCall(0).should.have.thrown("TypeError");
            }).to.not.throw();
        });
    });

    describe("always thrown", function () {
        var error = null;

        beforeEach(function () {
            error = new TypeError("boo!");
        });

        it("should throw an assertion error if the spy throws once but not the next time", function () {
            var spy = sinon.spy.create(function () {
                if (!(spy.callCount > 1)) {
                    throw error;
                }
            });

            swallow(spy);
            swallow(spy);

            expect(function () {
                spy.should.have.always.thrown();
            }).to.throw(AssertionError);
            expect(function () {
                spy.should.always.have.thrown();
            }).to.throw(AssertionError);
            expect(function () {
                spy.should.have.always.thrown(error);
            }).to.throw(AssertionError);
            expect(function () {
                spy.should.always.have.thrown(error);
            }).to.throw(AssertionError);
            expect(function () {
                spy.should.have.always.thrown("TypeError");
            }).to.throw(AssertionError);
            expect(function () {
                spy.should.always.have.thrown("TypeError");
            }).to.throw(AssertionError);
        });

        it("should throw an assertion error if the spy throws the wrong error the second time", function () {
            var spy = sinon.spy.create(function () {
                if (spy.callCount === 1) {
                    throw error;
                } else {
                    throw new Error();
                }
            });

            swallow(spy);
            swallow(spy);

            expect(function () {
                spy.should.have.always.thrown(error);
            }).to.throw(AssertionError);
            expect(function () {
                spy.should.always.have.thrown(error);
            }).to.throw(AssertionError);
            expect(function () {
                spy.should.have.always.thrown("TypeError");
            }).to.throw(AssertionError);
            expect(function () {
                spy.should.always.have.thrown("TypeError");
            }).to.throw(AssertionError);
        });

        it("should not throw if the spy always throws the right error", function () {
            var spy = sinon.spy.create(function () {
                throw error;
            });

            swallow(spy);
            swallow(spy);

            expect(function () {
                spy.should.have.always.thrown(error);
            }).to.not.throw();
            expect(function () {
                spy.should.always.have.thrown(error);
            }).to.not.throw();
            expect(function () {
                spy.should.have.always.thrown("TypeError");
            }).to.not.throw();
            expect(function () {
                spy.should.always.have.thrown("TypeError");
            }).to.not.throw();
        });
    });
});
