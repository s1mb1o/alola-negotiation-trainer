const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {join} = require('node:path');
const {JSDOM} = require('../../frontend/node_modules/jsdom');
const root = join(__dirname, '..', 'app', 'static');
const html = readFileSync(join(root, 'llm-debug.html'), 'utf8');
const script = readFileSync(join(root, 'llm-debug.js'), 'utf8');
const older = 'llm_' + 'a'.repeat(32);
const newer = 'llm_' + 'b'.repeat(32);
const missing = 'llm_' + 'c'.repeat(32);
function record(id, content) {
  return {trace_id:id, session_id:'sess_fixture', task:'npc_dialogue', model:'offline-fixture', provider:'fixture',
    status:'completed', duration_ms:100, started_at:'2026-09-24T12:00:00Z', instructions:'Reply in Russian.',
    messages:[{role:'user',content}], response:JSON.stringify({reply:content}), parameters:{}, usage:{}, retry_count:0,
    requests:[{attempt:1, method:'POST', url:'https://fixture.example/chat/completions', headers:{Authorization:'[REDACTED]'},
      body:{model:'offline-fixture', messages:[{role:'system',content:'Reply in Russian.'},{role:'user',content}], seed:42}}]};
}
async function until(condition) {
  for (let i = 0; i < 100; i++) { if (condition()) return; await new Promise(resolve => setTimeout(resolve, 5)); }
  throw new Error('UI did not reach the expected state');
}
function fixture(t, hash = '', options = {}) {
  const dom = new JSDOM(html, {url:'http://127.0.0.1:8172/llm-debug' + hash, runScripts:'outside-only'});
  t.after(() => dom.window.close());
  const {window} = dom, document = window.document;
  const data = new Map([[older,record(older,'Older response')], [newer,record(newer,'Newer response')]]);
  const requests = [];
  document.getElementById('auto').checked = false;
  window.HTMLElement.prototype.scrollIntoView = function () { this.dataset.scrolled = 'true'; };
  window.fetch = async (url) => {
    requests.push(url);
    if (options.fetch) { const result = await options.fetch(url); if (result) return result; }
    const id = url.split('/').at(-1);
    const isList = id.startsWith('llm-traces?');
    const result = isList ? {enabled:true,capacity:200,items:[...data.values()].reverse()} : data.get(id);
    return {ok:Boolean(result),status:result?200:404,json:async()=>result};
  };
  window.eval(script);
  return {window, document, requests, data};
}
function reply(document) { return document.querySelector('#response pre')?.textContent || ''; }

test('relevance checks have a distinct readable task label', async t => {
  const item = {...record(newer, 'Relevance verdict'), task:'npc_relevance'};
  const {document} = fixture(t, '#' + newer, {
    fetch: url => ({ok:true,status:200,json:async()=>url.includes('llm-traces?')
      ? {enabled:true,capacity:200,items:[item]} : item}),
  });
  await until(() => reply(document).includes('Relevance verdict'));
  assert.equal(document.getElementById('detail-title').textContent, 'Проверка уместности');
  assert.ok(document.querySelector('.call').textContent.includes('Проверка уместности'));
});

test('direct links restore an older record instead of the newest record', async t => {
  const {window,document,requests} = fixture(t, '#' + older);
  await until(() => reply(document).includes('Older response'));
  assert.equal(window.location.hash, '#' + older);
  assert.equal(document.querySelector('.call[aria-current=true]').hash, '#' + older);
  assert.ok(requests.some(url => url.endsWith('/' + older)));
  document.getElementById('refresh').click();
  await until(() => requests.filter(url => url.endsWith('/' + older)).length === 2);
  assert.equal(window.location.hash, '#' + older);
});

test('native links support call selection, browser back and forward', async t => {
  const {window,document} = fixture(t);
  await until(() => reply(document).includes('Newer response'));
  assert.equal(window.location.hash, '#' + newer);
  document.querySelector(`.call[href="/llm-debug#${older}"]`).click();
  await until(() => reply(document).includes('Older response'));
  assert.equal(window.location.hash, '#' + older);
  window.history.back();
  await until(() => reply(document).includes('Newer response'));
  window.history.forward();
  await until(() => reply(document).includes('Older response'));
});

test('every input and output has a section address, restored on page load', async t => {
  const {document} = fixture(t, '#' + older + '/message-0');
  await until(() => document.getElementById('message-0')?.dataset.scrolled === 'true');
  for (const section of ['request-0','instructions','message-0','response','parameters']) {
    assert.equal(document.querySelector(`#${section} a`).getAttribute('href'), `/llm-debug#${older}/${section}`);
  }
  document.querySelector('#response a').click();
  await until(() => document.getElementById('response')?.dataset.scrolled === 'true');
  const reloaded = fixture(t, '#' + older + '/response');
  await until(() => reloaded.document.getElementById('response')?.dataset.scrolled === 'true');
  assert.ok(reply(reloaded.document).includes('Older response'));
});

test('full outgoing JSON and retries retain long content and literal markup', async t => {
  const long = 'Я'.repeat(65000) + '<script>window.injected = true</script>TAIL';
  const item = record(older, long);
  item.requests.push({...item.requests[0],attempt:2});
  const {document,window} = fixture(t, '#' + older + '/request-1', {
    fetch: url => url.endsWith('/' + older) ? {ok:true,status:200,json:async()=>item} : undefined,
  });
  await until(() => document.getElementById('request-1')?.dataset.scrolled === 'true');
  const request = JSON.parse(document.querySelector('#request-1 pre').textContent);
  assert.equal(request.body.messages[1].content, long);
  assert.equal(request.headers.Authorization, '[REDACTED]');
  assert.equal(request.body.seed, 42);
  assert.equal(window.injected, undefined);
  assert.equal(document.querySelectorAll('#detail script').length, 0);
  assert.equal(document.getElementById('parameters').open, true);
  assert.equal(document.querySelector('#request-1 a').getAttribute('href'), `/llm-debug#${older}/request-1`);
});

test('missing and evicted records preserve the URL and never display another response', async t => {
  const {window,document,data,requests} = fixture(t, '#' + older);
  await until(() => reply(document).includes('Older response'));
  data.delete(older);
  document.getElementById('refresh').click();
  await until(() => document.getElementById('detail-title').textContent === 'Запись недоступна');
  assert.equal(window.location.hash, '#' + older);
  assert.equal(reply(document), '');
  assert.equal(document.getElementById('error').hidden, false);
  assert.ok(!requests.some(url => url.endsWith('/' + newer)));
  const absent = fixture(t, '#' + missing);
  await until(() => absent.document.getElementById('detail-title').textContent === 'Запись недоступна');
  assert.equal(absent.window.location.hash, '#' + missing);
});

test('navigation during an in-flight request cannot paint the previous record', async t => {
  let release;
  const {window,document,requests} = fixture(t, '#' + older, {fetch: url => url.endsWith('/' + older)
    ? new Promise(resolve => { release = () => resolve({ok:true,status:200,json:async()=>record(older,'Stale response')}); })
    : undefined});
  await until(() => release);
  window.location.hash = newer;
  await until(() => document.getElementById('detail-title').textContent === 'Загрузка вызова…');
  // Let the hashchange invalidate the previous request before it completes.
  await new Promise(resolve => setTimeout(resolve, 10));
  release();
  await until(() => reply(document).includes('Newer response'));
  assert.ok(!document.getElementById('detail').textContent.includes('Stale response'));
  assert.ok(requests.some(url => url.endsWith('/' + newer)));
});

test('invalid links and missing sections show explicit errors without changing addresses', async t => {
  const invalid = fixture(t, '#not-a-trace');
  await until(() => invalid.document.getElementById('detail-title').textContent === 'Неверная ссылка');
  assert.equal(invalid.window.location.hash, '#not-a-trace');
  assert.equal(reply(invalid.document), '');
  const absentSection = fixture(t, '#' + older + '/message-99');
  await until(() => absentSection.document.getElementById('error').textContent.includes('Раздел по этой ссылке отсутствует'));
  assert.equal(absentSection.window.location.hash, '#' + older + '/message-99');
});
