"use strict";

var fs = require("fs");
var path = require("path");
var vm = require("vm");

var document = {
  addEventListener: function () {},
  getElementById: function () { return { innerHTML: "", querySelector: function () { return null; }, querySelectorAll: function () { return []; }, addEventListener: function () {} }; },
  createElement: function () { return { innerHTML: "", firstElementChild: {}, querySelector: function () { return null; } }; },
  querySelector: function () { return null; },
  getElementsByTagName: function () { return []; },
};

var sandbox = {
  window: {},
  document: document,
  console: console,
  setTimeout: setTimeout,
  clearInterval: function () {},
  fetch: function () { return Promise.resolve({ ok: true, json: function () { return Promise.resolve([]); } }); },
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;

var src = fs.readFileSync(path.join(__dirname, "..", "templates", "app.js"), "utf8");
if (/\bimport\b/.test(src) || /\bexport\b/.test(src) || /\brequire\s*\(/.test(src)) {
  throw new Error("app.js must not use import/export/require");
}
vm.runInNewContext(src, sandbox);
if (!sandbox.Hsk5 || typeof sandbox.Hsk5.boot !== "function") {
  throw new Error("Hsk5.boot missing");
}
console.log("js-load ok Hsk5.boot");
