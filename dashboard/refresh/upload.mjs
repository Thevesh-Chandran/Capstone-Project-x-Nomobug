// Upload ./build to gs://<bucket>/site/ and remove files the new build no longer has.
// Runs inside the Cloud Run job; credentials come from the job's service account
// via the metadata server, so no key file is used.
import { readdir, readFile } from 'node:fs/promises';
import { join, relative, extname } from 'node:path';

const bucket = process.env.DASHBOARD_BUCKET;
const prefix = 'site/';
const root = new URL('../build/', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
if (!bucket) throw new Error('DASHBOARD_BUCKET is not set');

const types = {
	'.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.mjs': 'text/javascript',
	'.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png',
	'.ico': 'image/x-icon', '.wasm': 'application/wasm', '.parquet': 'application/octet-stream',
	'.webmanifest': 'application/manifest+json', '.txt': 'text/plain', '.woff2': 'font/woff2'
};

async function token() {
	const r = await fetch(
		'http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token',
		{ headers: { 'Metadata-Flavor': 'Google' } }
	);
	if (!r.ok) throw new Error(`metadata token ${r.status}`);
	return (await r.json()).access_token;
}

async function* walk(dir) {
	for (const e of await readdir(dir, { withFileTypes: true })) {
		const p = join(dir, e.name);
		if (e.isDirectory()) yield* walk(p);
		else yield p;
	}
}

const auth = { Authorization: `Bearer ${await token()}` };
const files = [];
for await (const f of walk(root)) files.push(f);
const keep = new Set();

async function put(file) {
	const name = prefix + relative(root, file).split('\\').join('/');
	keep.add(name);
	const url = `https://storage.googleapis.com/upload/storage/v1/b/${bucket}/o?uploadType=media&name=${encodeURIComponent(name)}`;
	for (let attempt = 1; attempt <= 3; attempt++) {
		const r = await fetch(url, {
			method: 'POST',
			headers: { ...auth, 'Content-Type': types[extname(file)] || 'application/octet-stream' },
			body: await readFile(file)
		});
		if (r.ok) return;
		if (attempt === 3) throw new Error(`upload ${name}: ${r.status} ${await r.text()}`);
	}
}

// Upload in small parallel batches; html last so pages never point at missing assets.
const html = files.filter((f) => f.endsWith('.html'));
const assets = files.filter((f) => !f.endsWith('.html'));
for (const group of [assets, html]) {
	for (let i = 0; i < group.length; i += 16) await Promise.all(group.slice(i, i + 16).map(put));
}

// Remove objects from older builds.
let pageToken = '';
let removed = 0;
do {
	const r = await fetch(
		`https://storage.googleapis.com/storage/v1/b/${bucket}/o?prefix=${prefix}&fields=items(name),nextPageToken${pageToken ? `&pageToken=${pageToken}` : ''}`,
		{ headers: auth }
	);
	const body = await r.json();
	for (const { name } of body.items || []) {
		if (!keep.has(name)) {
			await fetch(`https://storage.googleapis.com/storage/v1/b/${bucket}/o/${encodeURIComponent(name)}`, {
				method: 'DELETE',
				headers: auth
			});
			removed++;
		}
	}
	pageToken = body.nextPageToken || '';
} while (pageToken);

console.log(JSON.stringify({ status: 'PUBLISHED', uploaded: files.length, removed, at: new Date().toISOString() }));
