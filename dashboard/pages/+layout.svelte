<script>
	import '@evidence-dev/tailwind/fonts.css';
	import '../app.css';
	import { EvidenceDefaultLayout } from '@evidence-dev/core-components';
	import { showQueries } from '@evidence-dev/component-utilities/stores';
	// Management viewers never need the SQL panels.
	showQueries.set(false);
	export let data;
	import { onMount } from 'svelte';
	// Buttons such as "Open the call list" open the matching website page (the part with the actions).
	onMount(() => {
		const go = (e) => {
			const a = e.target.closest && e.target.closest('[data-to]');
			if (!a || (e.type === 'keydown' && e.key !== 'Enter')) return;
			e.preventDefault();
			try { window.top.location.hash = a.dataset.to; } catch (err) { window.location.href = '/#' + a.dataset.to; }
		};
		document.addEventListener('click', go);
		document.addEventListener('keydown', go);
		return () => { document.removeEventListener('click', go); document.removeEventListener('keydown', go); };
	});
</script>

<EvidenceDefaultLayout
	{data}
	title="Nomobug"
	homePageName="Overview"
	builtWithEvidence={false}
	neverShowQueries={true}
	hideTOC={true}
	hideBreadcrumbs={true}
	hideSidebar={true}
	hideHeader={true}
	maxWidth={1320}
>
	<slot slot="content" />
</EvidenceDefaultLayout>

<style>
	/* Hallmark · Dusk, shared with the staff website: a bone well for the working surface, white cards,
	   Wix Madefor Display over Wix Madefor Text, periwinkle for done and the action, apricot for open or owed */
	@font-face {
		font-family: 'Wix Madefor Display';
		src: url('/wix-madefor-display.woff2') format('woff2-variations'), url('/wix-madefor-display.woff2') format('woff2');
		font-weight: 400 800;
		font-display: swap;
	}
	@font-face {
		font-family: 'Wix Madefor Text';
		src: url('/wix-madefor-text.woff2') format('woff2-variations'), url('/wix-madefor-text.woff2') format('woff2');
		font-weight: 400 800;
		font-display: swap;
	}
	:global(:root) {
		--color-well: oklch(95.5% 0.008 75);
		--color-card: oklch(99.5% 0.003 75);
		--color-ink: oklch(21% 0.016 268);
		--color-ink-2: oklch(30% 0.016 268);
		--color-muted: oklch(47% 0.016 265);
		--color-rule: oklch(87.5% 0.009 75);
		--color-shell: oklch(17.5% 0.014 268);
		--color-shell-ink: oklch(96% 0.006 75);
		--color-shell-muted: oklch(70% 0.016 262);
		--color-signal: oklch(77% 0.10 274);
		--color-apricot: oklch(83% 0.095 62);
		--font-display: 'Wix Madefor Display', ui-sans-serif, system-ui, sans-serif;
		--font-body: 'Wix Madefor Text', ui-sans-serif, system-ui, sans-serif;
		--radius-card: 18px;
		--radius-inner: 10px;
		--series-1: #5B63C9;
		--series-2: #D97E45;
		--series-3: #2E9CB8;
		--series-4: #D9577A;
	}
	:global(html), :global(body) { overflow-x: clip; }
	:global(body), :global(main), :global(header) {
		background: var(--color-well) !important;
		color: var(--color-ink);
		font-family: var(--font-body) !important;
		font-variant-numeric: tabular-nums;
	}
	:global(article), :global(article *) { font-family: var(--font-body); }
	:global(h1.title) { display: none; }
	/* no empty band under the last card: the website's action band follows straight on */
	:global(article) { padding-bottom: 0 !important; margin-bottom: 0 !important; }
	:global(main) { padding-bottom: 8px !important; }
	:global(.table-footer) { display: none !important; }
	:global(article h2), :global(article h3), :global(.hero h1) { font-family: var(--font-display) !important; }
	:global(article h2) { font-weight: 500; font-size: 1.3rem; letter-spacing: -0.022em; margin-top: 1.8rem; color: var(--color-ink); }

	/* Page title: quiet display weight on the well, no box */
	:global(.hero) { padding: 4px 0 4px; margin: 0 0 22px; }
	:global(.hero h1) { font-size: 2.2rem; font-weight: 500; letter-spacing: -0.022em; line-height: 1.05; margin: 0 0 8px; color: var(--color-ink); overflow-wrap: break-word; min-width: 0; }
	:global(.hero p) { margin: 0; color: var(--color-muted); max-width: 62ch; line-height: 1.55; font-size: 1rem; }
	:global(.hero .chip) {
		display: inline-block; margin-top: 12px; padding: 4px 12px; border-radius: 999px;
		background: var(--color-card); border: 1px solid var(--color-rule); color: var(--color-ink-2); font-size: 0.8rem; font-weight: 500;
	}

	/* Figures in one ruled white card per figure */
	:global(.kpis) { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-bottom: 16px; }
	:global(.kpis.three) { grid-template-columns: repeat(3, minmax(0, 1fr)); }
	:global(.kpis.two) { grid-template-columns: repeat(2, minmax(0, 1fr)); }
	:global(.kpis > *) {
		background: var(--color-card); border: 1px solid var(--color-rule); border-radius: var(--radius-card);
		padding: 16px 18px 12px; margin: 0 !important; min-width: 0 !important; width: auto !important;
	}
	:global(.kpis > * p) { margin: 0; }
	/* a thin colour edge per figure, in the chart order: periwinkle, apricot, teal, rose */
	:global(.kpis > *:nth-child(4n+1)) { border-top: 3px solid var(--series-1); }
	:global(.kpis > *:nth-child(4n+2)) { border-top: 3px solid var(--series-2); }
	:global(.kpis > *:nth-child(4n+3)) { border-top: 3px solid var(--series-3); }
	:global(.kpis > *:nth-child(4n+4)) { border-top: 3px solid var(--series-4); }

	/* Charts and tables: white cards on the well */
	:global(.card) { background: var(--color-card); border: 1px solid var(--color-rule); border-radius: var(--radius-card); padding: 18px 20px 12px; margin-bottom: 16px; min-width: 0; }
	:global(.card h3) { font-family: var(--font-display); font-size: 1.05rem; font-weight: 500; letter-spacing: -0.015em; margin: 0 0 2px; color: var(--color-ink); }
	:global(.card .sub) { font-size: 0.82rem; color: var(--color-muted); margin: 0 0 10px; }
	:global(.row2) { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
	:global(.row3) { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }

	/* This week: slate cards, the figure in fog, the next step in periwinkle */
	:global(.action) { background: var(--color-shell); color: var(--color-shell-ink); border-radius: var(--radius-card); padding: 18px 20px; }
	:global(.action .label) { font-size: 0.82rem; font-weight: 500; color: var(--color-shell-muted); }
	:global(.action .big) { font-family: var(--font-display); font-size: 1.5rem; font-weight: 500; letter-spacing: -0.022em; line-height: 1.1; margin: 6px 0 8px; color: var(--color-shell-ink); }
	:global(.action p) { margin: 0 0 14px; color: var(--color-shell-muted); font-size: 0.88rem; line-height: 1.5; }
	:global(.action a), :global(a.go) {
		display: inline-flex; align-items: center; min-height: 36px; padding: 0 14px; border-radius: 999px; cursor: pointer;
		background: var(--color-signal); color: var(--color-shell); font-weight: 600; font-size: 0.86rem; text-decoration: none;
	}
	:global(a.go:hover) { background: var(--color-shell-ink); }
	:global(a.go:focus-visible) { outline: 2px solid var(--color-signal); outline-offset: 2px; }
	:global(.note) { font-size: 0.8rem; color: var(--color-muted); margin: 4px 2px 18px; }

	@media (max-width: 900px) {
		:global(.kpis), :global(.kpis.three), :global(.row2), :global(.row3) { grid-template-columns: repeat(2, minmax(0, 1fr)); }
	}
	@media (max-width: 560px) {
		:global(.kpis), :global(.kpis.three), :global(.kpis.two), :global(.row2), :global(.row3) { grid-template-columns: 1fr; }
	}
</style>
