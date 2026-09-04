(function (global) {
  "use strict";

  function el(html) {
    var d = global.document.createElement("div");
    d.innerHTML = html;
    return d.firstElementChild;
  }

  function $(sel, root) {
    return (root || global.document).querySelector(sel);
  }

  function fmt(n) {
    if (n === null || n === undefined) return "—";
    return Math.round(n * 10) / 10;
  }

  function hanziCount(s) {
    var n = 0, i, c;
    for (i = 0; i < s.length; i += 1) {
      c = s.charCodeAt(i);
      if (c >= 0x4e00 && c <= 0x9fff) n += 1;
    }
    return n;
  }

  function Hsk5() {}

  Hsk5.boot = function (root) {
    var state = { view: "list", exams: [], exam: null, attempt: null, answers: { mcq: {}, sentence: {}, essay: {} }, result: null, size: 10, section: "listening", remain: 0, timer: null };
    var BASE = "";
    (function () {
      var scripts = global.document.getElementsByTagName("script");
      var i, src;
      for (i = 0; i < scripts.length; i += 1) {
        src = scripts[i].getAttribute("src") || scripts[i].src || "";
        if (src.indexOf("app.js") >= 0) {
          BASE = src.replace(/\/app\.js(\?.*)?$/, "").replace(/^https?:\/\/[^/]+/, "");
          break;
        }
      }
    })();

    function api(path, opts) {
      return global.fetch(BASE + path, opts).then(function (r) {
        return r.json().then(function (j) {
          if (!r.ok) throw new Error(j.detail || r.status);
          return j;
        });
      });
    }

    function loadList() {
      return api("/api/exams").then(function (rows) {
        state.exams = rows;
        render();
      });
    }

    function startTimer(minutes) {
      if (state.timer) global.clearInterval(state.timer);
      state.remain = minutes * 60;
      state.timer = global.setInterval(function () {
        state.remain -= 1;
        var t = $(".timer");
        if (t) t.textContent = clock(state.remain);
        if (state.remain <= 0) global.clearInterval(state.timer);
      }, 1000);
    }

    function clock(sec) {
      if (sec < 0) sec = 0;
      var m = Math.floor(sec / 60);
      var s = sec % 60;
      return (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s;
    }

    function createExam() {
      api("/api/exams", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ size: state.size }),
      }).then(function (j) {
        state.view = "generating";
        state.pending = j.id;
        render();
        poll(j.id);
      });
    }

    function poll(id) {
      api("/api/exams/" + id).then(function (j) {
        if (j.status === "ready") {
          state.view = "list";
          loadList();
          return;
        }
        if (j.status === "failed") {
          state.view = "list";
          state.error = j.error || "生成失败";
          loadList();
          return;
        }
        state.progress = j.progress;
        render();
        global.setTimeout(function () { poll(id); }, 800);
      });
    }

    function begin(id) {
      api("/api/exams/" + id + "/attempts", { method: "POST" }).then(function (att) {
        return api("/api/exams/" + id).then(function (exam) {
          state.exam = exam;
          state.attempt = att;
          state.answers = { mcq: {}, sentence: {}, essay: {} };
          state.view = "take";
          state.section = exam.listening && exam.listening.length ? "listening" : exam.reading && exam.reading.length ? "reading" : "writing";
          var limits = exam.limits || {};
          var mins = limits[state.section + "_minutes"] || 1;
          startTimer(mins);
          render();
        });
      }).catch(function (e) {
        state.error = String(e.message || e);
        render();
      });
    }

    function nextSection() {
      if (state.section === "listening" && state.exam.reading && state.exam.reading.length) {
        state.section = "reading";
        startTimer(state.exam.limits.reading_minutes || 1);
        render();
        return;
      }
      if (state.section !== "writing" && ((state.exam.sentence_order && state.exam.sentence_order.length) || (state.exam.essays && state.exam.essays.length))) {
        state.section = "writing";
        startTimer(state.exam.limits.writing_minutes || 1);
        render();
        return;
      }
      submit();
    }

    function submit() {
      if (state.timer) global.clearInterval(state.timer);
      api("/api/attempts/" + state.attempt.attempt_id + "/submit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(state.answers),
      }).then(function (j) {
        state.result = j.result;
        state.view = "result";
        render();
      }).catch(function (e) {
        state.error = String(e.message || e);
        render();
      });
    }

    function renderList() {
      var cards = state.exams.map(function (e) {
        var best = e.best_total == null ? "—" : fmt(e.best_total);
        var meta = "ID " + e.id + "　サイズ " + e.size + "%　" + (e.created_at || "");
        var score = "最高点 " + best + (e.best_at ? "（" + e.best_at + "）" : "");
        var action;
        if (e.status === "ready") {
          action = "<button class=\"primary start-btn\" data-start=\"" + e.id + "\">試験開始</button>";
        } else if (e.status === "generating") {
          action = "<p class=\"hint\">生成中… " + (e.progress || "") + "</p>";
        } else {
          action = "<p class=\"hint\">生成失敗" + (e.error ? "（" + e.error + "）" : "") + "。上から作り直す。</p>";
        }
        return "<article class=\"exam-card\"><p class=\"exam-meta\">" + meta + "</p><p class=\"exam-score\">" + score + "</p>" + action + "</article>";
      }).join("");
      root.innerHTML =
        "<div class=\"admit\"><span>模擬試験</span><strong>一覧</strong></div>" +
        (state.error ? "<p class=\"hint\">" + state.error + "</p>" : "") +
        "<div class=\"row\"><label class=\"size\">サイズ <input id=\"size\" type=\"range\" min=\"1\" max=\"100\" value=\"" + state.size + "\"> <span id=\"sizev\">" + state.size + "%</span></label>" +
        "<button class=\"primary\" id=\"make\">試験を作る</button></div>" +
        (state.exams.length ? cards : "<p class=\"empty\">試験が無い。サイズを選んで「試験を作る」。</p>");
      var slider = $("#size", root);
      slider.addEventListener("input", function () {
        state.size = parseInt(slider.value, 10);
        $("#sizev", root).textContent = state.size + "%";
      });
      $("#make", root).addEventListener("click", createExam);
      root.querySelectorAll("[data-start]").forEach(function (b) {
        b.addEventListener("click", function () { begin(b.getAttribute("data-start")); });
      });
    }

    function renderGenerating() {
      root.innerHTML = "<div class=\"admit\"><span>生成中</span><strong>" + (state.pending || "") + "</strong></div><p>問題を作っている。数分かかることがある。</p><p class=\"hint\">" + (state.progress || "") + "</p>";
    }

    function bubbles(item) {
      return "<div class=\"bubbles\">" + item.choices.map(function (c) {
        var chk = state.answers.mcq[item.id] === c.key ? " checked" : "";
        return "<label><input type=\"radio\" name=\"" + item.id + "\" value=\"" + c.key + "\"" + chk + "><span><b>" + c.key + "</b> " + c.text + "</span></label>";
      }).join("") + "</div>";
    }

    function renderTake() {
      var exam = state.exam;
      var html = (state.error ? "<p class=\"hint\">" + state.error + "</p>" : "") +
        "<div class=\"admit\"><span>准考证号　" + exam.id + "</span><strong class=\"timer\" id=\"timer\">" + clock(state.remain) + "</strong></div>";
      html += "<div class=\"section-h\"><h2>" + (state.section === "listening" ? "听力" : state.section === "reading" ? "阅读" : "书写") + "</h2><span class=\"hint\">" + exam.size + "%</span></div>";
      var i;
      if (state.section === "listening") {
        for (i = 0; i < exam.listening.length; i += 1) {
          var L = exam.listening[i];
          html += "<div class=\"item\"><span class=\"qno\">" + (i + 1) + "</span>";
          if (L.clip_id) html += "<audio controls src=\"" + BASE + "/api/exams/" + exam.id + "/audio/" + L.clip_id + "\"></audio>";
          html += bubbles(L) + "</div>";
        }
      } else if (state.section === "reading") {
        for (i = 0; i < exam.reading.length; i += 1) {
          var R = exam.reading[i];
          html += "<div class=\"item\"><span class=\"qno\">" + (i + 1) + "</span>";
          if (R.passage) html += "<div class=\"passage\">" + R.passage + "</div>";
          if (R.prompt) html += "<p>" + R.prompt + "</p>";
          html += bubbles(R) + "</div>";
        }
      } else {
        for (i = 0; i < (exam.sentence_order || []).length; i += 1) {
          var S = exam.sentence_order[i];
          html += "<div class=\"item\"><span class=\"qno\">" + (i + 1) + "</span><p>连词成句</p><div class=\"chips\" data-sent=\"" + S.id + "\">";
          S.words.forEach(function (w, idx) {
            html += "<button type=\"button\" class=\"chip\" data-w=\"" + idx + "\">" + w + "</button>";
          });
          html += "</div><p class=\"hint\" data-preview=\"" + S.id + "\"></p></div>";
        }
        for (i = 0; i < (exam.essays || []).length; i += 1) {
          var E = exam.essays[i];
          html += "<div class=\"item\"><span class=\"qno\">" + (i + 1) + "</span>";
          if (E.kind === "keywords") html += "<p>用下列词语写一篇 80 字左右的短文：<b>" + (E.required_words || []).join("、") + "</b></p>";
          if (E.kind === "picture") {
            html += "<p>根据图片写一篇 80 字左右的短文。</p>";
            if (E.image_url) html += "<img class=\"pic\" alt=\"看图\" src=\"" + E.image_url + "\">";
          }
          html += "<textarea data-essay=\"" + E.id + "\">" + (state.answers.essay[E.id] || "") + "</textarea><p class=\"hanzi\" data-hc=\"" + E.id + "\">0 字</p></div>";
        }
      }
      html += "<div class=\"row\"><button class=\"primary\" id=\"next\">" + (state.section === "writing" || (!exam.reading.length && state.section === "listening") ? "交卷" : "下一节") + "</button></div>";
      root.innerHTML = html;
      root.querySelectorAll("input[type=radio]").forEach(function (inp) {
        inp.addEventListener("change", function () { state.answers.mcq[inp.name] = inp.value; });
      });
      root.querySelectorAll("[data-sent]").forEach(function (box) {
        var id = box.getAttribute("data-sent");
        var item = null;
        (state.exam.sentence_order || []).forEach(function (s) { if (s.id === id) item = s; });
        var picked = [];
        box.querySelectorAll(".chip").forEach(function (ch) {
          ch.addEventListener("click", function () {
            var idx = parseInt(ch.getAttribute("data-w"), 10);
            var pos = picked.indexOf(idx);
            if (pos >= 0) {
              ch.className = "chip";
              picked.splice(pos, 1);
            } else {
              ch.className = "chip on";
              picked.push(idx);
            }
            var words = item ? picked.map(function (i) { return item.words[i]; }) : [];
            state.answers.sentence[id] = words.join("");
            var p = root.querySelector("[data-preview=\"" + id + "\"]");
            if (p) p.textContent = words.join("");
          });
        });
      });
      root.querySelectorAll("[data-essay]").forEach(function (ta) {
        function upd() {
          state.answers.essay[ta.getAttribute("data-essay")] = ta.value;
          var h = root.querySelector("[data-hc=\"" + ta.getAttribute("data-essay") + "\"]");
          if (h) h.textContent = hanziCount(ta.value) + " 字";
        }
        ta.addEventListener("input", upd);
        upd();
      });
      $("#next", root).addEventListener("click", nextSection);
    }

    function reviewHtml(r) {
      var html = "";
      function mcqBlock(title, items) {
        if (!items || !items.length) return "";
        var rows = items.map(function (it, i) {
          return "<div class=\"item\"><span class=\"qno\">" + (i + 1) + "</span>" +
            (it.correct ? "正" : "誤") + "　答 " + (it.answer || "") +
            (it.transcript ? "<div class=\"passage\">" + it.transcript + "</div>" : "") +
            (it.comment_ja ? "<p class=\"hint\">" + it.comment_ja + "</p>" : "") +
            "</div>";
        }).join("");
        return "<div class=\"section-h\"><h2>" + title + "</h2></div>" + rows;
      }
      html += mcqBlock("听力 回顾", r.listening_items);
      html += mcqBlock("阅读 回顾", r.reading_items);
      if (r.sentence_items && r.sentence_items.length) {
        html += "<div class=\"section-h\"><h2>连词成句</h2></div>";
        r.sentence_items.forEach(function (it, i) {
          html += "<div class=\"item\"><span class=\"qno\">" + (i + 1) + "</span>" +
            (it.correct ? "正" : "誤") + "　" + (it.gold || "") + "</div>";
        });
      }
      if (r.essay_items && r.essay_items.length) {
        html += "<div class=\"section-h\"><h2>作文</h2></div>";
        r.essay_items.forEach(function (it, i) {
          html += "<div class=\"item\"><span class=\"qno\">" + (i + 1) + "</span>" +
            (it.band || "") + "　" + fmt(it.points) + "点" +
            (it.comment_ja ? "<p>" + it.comment_ja + "</p>" : "") + "</div>";
        });
      }
      return html;
    }

    function renderResult() {
      var r = state.result;
      root.innerHTML =
        "<div class=\"admit\"><span>成绩报告</span><strong>" + state.exam.id + "</strong></div>" +
        "<div class=\"scores\">" +
        "<div>听力<strong>" + fmt(r.listening) + "</strong></div>" +
        "<div>阅读<strong>" + fmt(r.reading) + "</strong></div>" +
        "<div>书写<strong>" + fmt(r.writing) + "</strong></div>" +
        "<div>总分<strong>" + fmt(r.total) + "</strong></div></div>" +
        "<p class=\"hint\">目安 180 / 300（不是及格判定）" + (r.overtime ? " · 时间超过" : "") + "</p>" +
        reviewHtml(r) +
        "<div class=\"row\"><button id=\"back\">返回一览</button></div>";
      $("#back", root).addEventListener("click", function () {
        state.view = "list";
        loadList();
      });
    }

    function render() {
      if (state.view === "generating") renderGenerating();
      else if (state.view === "take") renderTake();
      else if (state.view === "result") renderResult();
      else renderList();
    }

    loadList();
  };

  global.Hsk5 = Hsk5;
  if (global.document && global.document.addEventListener) {
    global.document.addEventListener("DOMContentLoaded", function () {
      var root = global.document.getElementById("app");
      if (root) Hsk5.boot(root);
    });
  }
})(typeof window !== "undefined" ? window : this);
