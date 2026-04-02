///JS 1: feedback_filter (create [js] object named exactly “feedback_filter” and paste this script)

JavaScriptinlets = 1; outlets = 1;
var generated = [];
var ignore_window = 150;

function list(p, v) {
    if (v === 0) return;
    var now = new Date().getTime();
    while (generated.length && generated[0].t < now - 1000) generated.shift();
    for (var i = 0; i < generated.length; i++) {
        if (generated[i].p === p && Math.abs(generated[i].v - v) < 20 && now - generated[i].t < ignore_window) {
            return; // Disklavier echo ignored
        }
    }
    outlet(0, p, v);
}

function ignore(ms) { ignore_window = Math.max(50, ms); post("Ignore window:", ignore_window, "ms\n"); }
function clear() { generated = []; post("Generated note cache cleared\n"); }
JS 2: abeyance_buffer (create [js] object named exactly “abeyance_buffer” and paste this script)
JavaScriptinlets = 1; outlets = 1;
var window_ms = 1500; var overlap_threshold = 50; var events = [];

function a() { add("a"); } function b() { add("b"); } function c() { add("c"); }
function d() { add("d"); } function e() { add("e"); } function f() { add("f"); }
function g() { add("g"); }

function window(ms) { window_ms = Math.max(100, ms); }

function add(elem) {
    var now = new Date().getTime();
    events.push({t: now, e: elem});
    prune(now);
    outlet(0, computeState(now));
}

function prune(now) { while (events.length && events[0].t < now - window_ms) events.shift(); }

function computeState(now) {
    var counts = {a:0,b:0,c:0,d:0,e:0,f:0,g:0};
    var distinct = 0, overlap = 0, total = events.length;
    for (var i = 0; i < events.length; i++) {
        var ev = events[i];
        if (counts[ev.e] === 0) distinct++;
        counts[ev.e]++;
        for (var j = 0; j < i; j++) {
            if (Math.abs(events[j].t - ev.t) < overlap_threshold && events[j].e !== ev.e) overlap = 1;
        }
    }
    return [counts.a, counts.b, counts.c, counts.d, counts.e, counts.f, counts.g, distinct, overlap, total];
}

function bang() { var now = new Date().getTime(); prune(now); outlet(0, computeState(now)); }
