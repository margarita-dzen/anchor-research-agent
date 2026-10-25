// kie gpt-image-2 runner, който не таксува два пъти (01.10.2026).
// Поводът: на 30.09 kie_runner.mjs при „terminated" (прекъснато сваляне на 6 MB PNG) подаваше задачата наново
// и всяко повторение се таксуваше: 1 480 кредита за 10 визии.
// Тук: taskId се пази в <jobs>.tasks.json веднага след createTask; при ново пускане се продължава poll-ът на
// същата задача. Свалянето се повтаря по същия URL. Нова задача се подава само при отказ от kie (state fail).
// node kie_runner2.mjs jobs.json [--gap 1500] [--inflight 20] [--tries 3]
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

const args = process.argv.slice(2);
const opt = (k, d) => { const i = args.indexOf('--' + k); return i >= 0 ? Number(args[i + 1]) : d; };
const GAP = opt('gap', 1500), INFLIGHT = opt('inflight', 20), TRIES = opt('tries', 3);
// Ключът: env KIE_AI_API_KEY, иначе файлът от env KIE_ENV (по подразбиране ~/ads-automation/.env). Никога в репото.
const KEY = process.env.KIE_AI_API_KEY || fs.readFileSync(process.env.KIE_ENV || (process.env.HOME + '/ads-automation/.env'), 'utf8').match(/^KIE_AI_API_KEY=(.+)$/m)[1].trim().replace(/"/g, '');
const H = { Authorization: 'Bearer ' + KEY, 'Content-Type': 'application/json' };
const RES = process.env.GPT2_RESOLUTION || '2K';
const JOBS = args[0];
const TASKS = JOBS.replace(/\.json$/, '') + '.tasks.json';
const tasks = fs.existsSync(TASKS) ? JSON.parse(fs.readFileSync(TASKS, 'utf8')) : {};
const saveTasks = () => fs.writeFileSync(TASKS, JSON.stringify(tasks, null, 1));
const jobs = JSON.parse(fs.readFileSync(JOBS, 'utf8')).filter(j => !fs.existsSync(j.outPath));
const clean = p => String(p).replace(/#[0-9a-fA-F]{6}\b/g, '').replace(/\s{2,}/g, ' ').trim();
const sleep = ms => new Promise(r => setTimeout(r, ms));
console.log(`RUNNER2: ${jobs.length} jobs, ${Object.keys(tasks).length} known tasks`);

let lastSubmit = 0, ok = 0, bad = 0;
async function submit(job) {
  for (let n = 0; ; n++) {
    const wait = lastSubmit + GAP - Date.now();
    if (wait > 0) { await sleep(wait); continue; }
    lastSubmit = Date.now();
    const input = { prompt: clean(job.prompt), aspect_ratio: job.ratio || '1:1', resolution: RES, input_urls: (job.filesUrl && job.filesUrl.length) ? job.filesUrl : undefined };
    let j;
    try {
      const r = await fetch('https://api.kie.ai/api/v1/jobs/createTask', { method: 'POST', headers: H, body: JSON.stringify({ model: (job.filesUrl && job.filesUrl.length) ? 'gpt-image-2-image-to-image' : 'gpt-image-2-text-to-image', input }) });
      j = await r.json();
    } catch (e) {
      // мрежова грешка при подаване: не знаем дали е минало, затова спираме тази задача, вместо да таксуваме два пъти
      throw new Error('create network: ' + e.message);
    }
    if (j.code === 200 && j.data?.taskId) return j.data.taskId;
    const msg = j.msg || JSON.stringify(j).slice(0, 150);
    if (/frequency|too many|rate/i.test(msg) && n < 30) { await sleep(10000); continue; }
    throw new Error('create: ' + msg);
  }
}
async function poll(id) {
  const t0 = Date.now();
  while (Date.now() - t0 < 40 * 60000) {
    await sleep(8000);
    try {
      const r = await fetch('https://api.kie.ai/api/v1/jobs/recordInfo?taskId=' + id, { headers: { ...H, 'User-Agent': 'Mozilla/5.0' } });
      const d = (await r.json()).data || {};
      if (d.state === 'success') return JSON.parse(d.resultJson).resultUrls[0];
      if (d.state === 'fail') throw new Error('task: ' + (d.failMsg || 'fail'));
    } catch (e) { if (/^task:/.test(e.message)) throw e; }
  }
  throw new Error('poll timeout ' + id);
}
async function download(url, out) {
  for (let t = 1; t <= 8; t++) {
    try {
      const r = await fetch(url);
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const buf = Buffer.from(await r.arrayBuffer());
      if (buf.length < 50000) throw new Error('short ' + buf.length);
      fs.mkdirSync(path.dirname(out), { recursive: true });
      fs.writeFileSync(out, buf);
      return;
    } catch (e) { console.log(`  download retry ${t} ${path.basename(out)}: ${e.message}`); await sleep(5000 * t); }
  }
  throw new Error('download failed');
}
async function run(job) {
  // ключ = файл + хеш на промпта: сменен промпт за същия файл е нова задача, не стария резултат
  const key = path.basename(job.outPath) + ':' + crypto.createHash('sha1').update(job.prompt + JSON.stringify((job.filesUrl||[]).map(u => path.basename(u)))).digest('hex').slice(0, 10);
  for (let t = 1; t <= TRIES; t++) {
    try {
      if (!tasks[key]) { tasks[key] = await submit(job); saveTasks(); }
      const url = await poll(tasks[key]);
      await download(url, job.outPath);
      ok++; console.log(`DONE ${ok}/${jobs.length} ${key} (try ${t})`);
      return;
    } catch (e) {
      console.log(`FAIL ${key} try ${t}: ${e.message.slice(0, 140)}`);
      if (/^task:/.test(e.message)) { delete tasks[key]; saveTasks(); continue; } // kie отказа: само тогава нова задача
      break; // мрежа / timeout: задачата остава в tasks.json, следващото пускане продължава poll-а
    }
  }
  bad++; console.log(`GAVEUP ${key}`);
}
const q = [...jobs];
await Promise.all(Array.from({ length: INFLIGHT }, async () => { while (q.length) await run(q.shift()); }));
console.log(`RUNNER_DONE ok=${ok} gaveup=${bad}`);
