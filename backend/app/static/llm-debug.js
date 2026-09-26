'use strict';
const el = (id) => document.getElementById(id);
const tasks = {npc_dialogue:'Ответ NPC', npc_grounding:'Проверка ответа', social:'Социальная реакция', coaching:'Разбор результата', supply_extraction:'Разбор предложения'};
const statuses = {running:'Ожидание модели', completed:'Ответ получен', error:'Ошибка провайдера'};
const routePattern = /^#(llm_[a-f0-9]{32})(?:\/(instructions|message-\d+|request-\d+|response|parameters))?$/;
let credential = '', selected = '', selectedSection = '', timer, busy = false, refreshQueued = false, generation = 0, detailVersion = 0;
let listSignature = '', detailSignature = '';

function traceLink(id, section = '') { return '/llm-debug#' + id + (section ? '/' + section : ''); }
function readRoute() {
  const match = window.location.hash.match(routePattern);
  return {id: match?.[1] || '', section: match?.[2] || '', invalid: Boolean(window.location.hash && !match)};
}
async function api(path) {
  const response = await fetch('/api/v1/admin/llm-traces' + path, {headers:credential ? {Authorization:'Bearer ' + credential} : {}, cache:'no-store'});
  if (!response.ok) {
    const messages = {401:'Ключ администратора не подошёл.', 503:'На сервере не настроен NEGOTIATION_ADMIN_TOKEN.', 404:'Запись по этой ссылке недоступна: журнал мог быть очищен при перезапуске или запись вышла за пределы последних вызовов. Выберите другой вызов.'};
    const error = new Error(messages[response.status] || 'Не удалось получить журнал. Проверьте подключение к API.');
    error.status = response.status;
    throw error;
  }
  return response.json();
}
function showError(error) { el('error').textContent = error.message; el('error').hidden = false; }
function node(tag, text, className) {
  const item = document.createElement(tag); item.textContent = text;
  if (className) item.className = className;
  return item;
}
function clearDetail(title = 'Выберите вызов') {
  detailSignature = '';
  el('detail').replaceChildren(); el('detail-title').textContent = title;
}
function panel(title, value, open, section) {
  const item = document.createElement('details'); item.open = open; item.id = section;
  const summary = node('summary', title);
  const link = node('a', 'Ссылка', 'section-link');
  link.href = traceLink(selected, section); link.setAttribute('aria-label', 'Ссылка: ' + title);
  summary.append(link);
  item.append(summary, node('pre', typeof value === 'string' ? value : JSON.stringify(value, null, 2)));
  return item;
}
function focusSection() {
  if (!selectedSection) return;
  const section = el(selectedSection);
  if (!section) { showError(new Error('Раздел по этой ссылке отсутствует в выбранном вызове.')); return; }
  section.open = true;
  section.scrollIntoView({block:'nearest'});
}
async function detail(id) {
  const version = ++detailVersion, run = generation;
  try {
    const item = await api('/' + encodeURIComponent(id));
    if (version !== detailVersion || run !== generation || id !== selected) return;
    const signature = JSON.stringify(item);
    if (signature === detailSignature) return;
    detailSignature = signature;
    el('detail-title').textContent = tasks[item.task] || item.task;
    const area = el('detail');
    const opened = new Map(Array.from(area.querySelectorAll('details')).map(item => [item.id, item.open]));
    area.replaceChildren(node('p', `${statuses[item.status]} · ${item.model} · ${item.duration_ms === null ? 'выполняется' : (item.duration_ms / 1000).toFixed(2) + ' с'}`, 'badge'));
    const permalink = node('a', 'Ссылка на вызов'); permalink.href = traceLink(item.trace_id);
    area.append(permalink, node('p', item.session_id, 'muted'));
    if (item.request_truncated || item.response_truncated) area.append(node('p', 'Длинное содержимое сокращено. Секреты скрыты до сокращения.', 'muted'));
    else area.append(node('p', 'Содержимое показано полностью. Значения ключей доступа скрыты.', 'muted'));
    const requests = item.requests || [];
    if (!requests.length) area.append(node('p', 'Отправка HTTP-запроса ещё не зафиксирована. Ниже показан вход адаптера модели.', 'muted'));
    requests.forEach((request, index) => {
      const section = 'request-' + index;
      area.append(panel(`Полный запрос → провайдер · попытка ${request.attempt}`, request, opened.get(section) ?? true, section));
    });
    area.append(panel('Инструкции модели', item.instructions, opened.get('instructions') ?? true, 'instructions'));
    item.messages.forEach((message, index) => {
      const section = 'message-' + index;
      const value = Object.keys(message).some(key => !['role','content'].includes(key)) ? message : message.content;
      area.append(panel(`Сообщение → LLM · ${index + 1} (${message.role})`, value, opened.get(section) ?? true, section));
    });
    let response = item.response ?? (item.status === 'running' ? 'Ожидание ответа…' : 'Ответ не получен.');
    try { response = JSON.parse(response); } catch { /* Show non-JSON responses as text. */ }
    area.append(panel('Ответ ← LLM', response, opened.get('response') ?? true, 'response'));
    area.append(panel('Параметры и диагностика', {trace_id:item.trace_id, provider:item.provider, started_at:item.started_at, parameters:item.parameters, usage:item.usage, error_type:item.error_type, http_status:item.http_status, retry_count:item.retry_count}, opened.get('parameters') ?? true, 'parameters'));
    focusSection();
  } catch (error) {
    if (version === detailVersion && run === generation && id === selected) {
      clearDetail(error.status === 404 ? 'Запись недоступна' : 'Не удалось загрузить вызов');
      showError(error);
    }
  }
}
async function refresh() {
  clearTimeout(timer);
  if (busy) { refreshQueued = true; return; }
  busy = true; const run = generation;
  try {
    const session = el('session').value.trim();
    const result = await api('?limit=200' + (session ? '&session_id=' + encodeURIComponent(session) : ''));
    if (run !== generation) return;
    el('access').hidden = true; el('viewer').hidden = false; el('error').hidden = true;
    el('logout').hidden = !credential;
    el('connection').textContent = result.enabled ? 'Подключено · ' + new Date().toLocaleTimeString('ru-RU') : 'Запись отключена';
    const memoryLimit = result.capacity_bytes ? ` и ${Math.round(result.capacity_bytes / 1024 / 1024)} МиБ` : '';
    el('retention').textContent = result.enabled ? `До ${result.capacity} вызовов${memoryLimit} в памяти процесса. При заполнении удаляются старые записи целиком. После перезапуска журнал очищается.` : 'Чтобы записывать новые вызовы, запустите API с NEGOTIATION_LLM_TRACE=true.';
    el('count').textContent = result.items.length;
    // An explicit address remains selected even if it is missing from the filtered list.
    if (!selected && !window.location.hash && result.items.length) {
      selected = result.items[0].trace_id;
      window.history.replaceState(null, '', traceLink(selected));
    }
    const list = el('calls');
    const signature = JSON.stringify([result.items, selected]);
    if (signature !== listSignature) {
      listSignature = signature;
      list.replaceChildren();
      if (!result.items.length) list.append(node('p', 'Вызовов пока нет. Отправьте новое сообщение в тренажёре.', 'muted'));
      for (const item of result.items) {
        const link = node('a', '', 'call'); link.href = traceLink(item.trace_id); link.setAttribute('aria-current', String(item.trace_id === selected));
        link.append(node('span', tasks[item.task] || item.task), node('span', `${statuses[item.status]} · ${new Date(item.started_at).toLocaleTimeString('ru-RU')}`, 'meta'), node('span', item.session_id, 'meta'));
        list.append(link);
      }
    }
    if (readRoute().invalid) { clearDetail('Неверная ссылка'); showError(new Error('В ссылке указан неверный идентификатор вызова или раздела.')); }
    else if (selected) await detail(selected);
    else clearDetail();
  } catch (error) {
    if (run === generation) {
      showError(error); el('connection').textContent = 'Ошибка подключения';
      if (error.status === 401 || error.status === 503) { el('access').hidden = false; el('viewer').hidden = true; }
    }
  }
  finally {
    busy = false;
    if (refreshQueued) { refreshQueued = false; refresh(); }
    else if (run === generation && el('auto').checked && !el('viewer').hidden) timer = setTimeout(refresh, 2000);
  }
}
function navigate() {
  const route = readRoute();
  generation++; detailVersion++;
  selected = route.id; selectedSection = route.section;
  clearDetail(selected ? 'Загрузка вызова…' : 'Выберите вызов');
  refresh();
}
window.addEventListener('hashchange', navigate);
el('login').addEventListener('submit', (event) => { event.preventDefault(); credential = el('credential').value.trim(); el('credential').value = ''; refresh(); });
el('refresh').addEventListener('click', refresh);
el('session').addEventListener('change', refresh);
el('auto').addEventListener('change', () => { clearTimeout(timer); if (el('auto').checked) refresh(); });
el('logout').addEventListener('click', () => { generation++; detailVersion++; clearTimeout(timer); refreshQueued = false; credential = ''; listSignature = ''; clearDetail(); el('viewer').hidden = true; el('access').hidden = false; el('calls').replaceChildren(); el('error').hidden = true; el('connection').textContent = 'Нет подключения'; });
navigate();
