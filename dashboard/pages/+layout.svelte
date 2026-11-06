<script>
	import '@evidence-dev/tailwind/fonts.css';
	import '../app.css';
	import { EvidenceDefaultLayout } from '@evidence-dev/core-components';
	import { showQueries } from '@evidence-dev/component-utilities/stores';
	// Management viewers never need the SQL panels.
	showQueries.set(false);
	export let data;
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
	/* Nomobug website tokens */
	:global(:root) {
		--nb-ink: #0f141d;
		--nb-ink-2: #1c2433;
		--nb-paper: #f3f7fa;
		--nb-card: #ffffff;
		--nb-rule: #dbe0e6;
		--nb-muted: #5b6474;
		--nb-blue: #2c6be7;
		--nb-sky: #e3f3ff;
		--nb-green: #009778;
		--nb-amber: #e78c08;
		--nb-red: #e24a3f;
	}
	:global(body),
	:global(main),
	:global(header) {
		background: var(--nb-paper) !important;
	}
	:global(h1.title) {
		display: none;
	}
	:global(article h2) {
		font-size: 1.05rem;
		font-weight: 650;
		margin-top: 1.6rem;
		color: var(--nb-ink);
	}

	/* Hero banner at the top of each page */
	:global(.hero) {
		background: linear-gradient(135deg, #0f141d 0%, #1c2a48 60%, #2c6be7 140%);
		color: #fff;
		border-radius: 18px;
		padding: 26px 30px;
		margin: 6px 0 18px;
		box-shadow: 0 10px 30px -12px rgba(15, 20, 29, 0.45);
	}
	:global(.hero h1) {
		font-size: 1.7rem;
		font-weight: 700;
		margin: 0 0 6px;
		color: #fff;
		letter-spacing: -0.01em;
	}
	:global(.hero p) {
		margin: 0;
		color: #c3e0fd;
		max-width: 70ch;
		line-height: 1.5;
	}
	:global(.hero .chip) {
		display: inline-block;
		margin-top: 12px;
		padding: 3px 10px;
		border-radius: 99px;
		background: rgba(255, 255, 255, 0.12);
		color: #e3f3ff;
		font-size: 0.78rem;
	}

	/* KPI row: every BigValue becomes a card */
	:global(.kpis) {
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		gap: 14px;
		margin-bottom: 14px;
	}
	:global(.kpis.three) {
		grid-template-columns: repeat(3, minmax(0, 1fr));
	}
	:global(.kpis.two) {
		grid-template-columns: repeat(2, minmax(0, 1fr));
	}
	:global(.kpis > *) {
		background: var(--nb-card);
		border: 1px solid var(--nb-rule);
		border-radius: 14px;
		padding: 14px 16px 10px;
		box-shadow: 0 1px 2px rgba(15, 20, 29, 0.05), 0 6px 16px -10px rgba(15, 20, 29, 0.25);
		min-width: 0 !important;
		width: auto !important;
		margin: 0 !important;
	}
	:global(.kpis > * p) {
		margin: 0;
	}

	/* Cards for charts and tables */
	:global(.card) {
		background: var(--nb-card);
		border: 1px solid var(--nb-rule);
		border-radius: 16px;
		padding: 16px 18px 10px;
		box-shadow: 0 1px 2px rgba(15, 20, 29, 0.05), 0 8px 22px -14px rgba(15, 20, 29, 0.3);
		margin-bottom: 14px;
		min-width: 0;
	}
	:global(.card h3) {
		font-size: 0.95rem;
		font-weight: 650;
		margin: 0 0 2px;
		color: var(--nb-ink);
	}
	:global(.card .sub) {
		font-size: 0.8rem;
		color: var(--nb-muted);
		margin: 0 0 8px;
	}
	:global(.row2) {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 14px;
	}
	:global(.row3) {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 14px;
	}

	/* Action cards */
	:global(.action) {
		border-radius: 14px;
		padding: 16px 18px;
		border: 1px solid var(--nb-rule);
		background: var(--nb-card);
		border-top: 4px solid var(--nb-blue);
		box-shadow: 0 6px 16px -10px rgba(15, 20, 29, 0.25);
	}
	:global(.action.green) {
		border-top-color: var(--nb-green);
	}
	:global(.action.amber) {
		border-top-color: var(--nb-amber);
	}
	:global(.action .label) {
		font-size: 0.72rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--nb-muted);
	}
	:global(.action .big) {
		font-size: 1.15rem;
		font-weight: 700;
		margin: 4px 0;
		color: var(--nb-ink);
	}
	:global(.action p) {
		margin: 0 0 8px;
		color: var(--nb-muted);
		font-size: 0.88rem;
	}
	:global(.action a) {
		font-weight: 600;
		color: var(--nb-blue);
		font-size: 0.88rem;
	}
	:global(.note) {
		font-size: 0.78rem;
		color: var(--nb-muted);
		margin: 4px 2px 18px;
	}

	@media (max-width: 900px) {
		:global(.kpis),
		:global(.kpis.three),
		:global(.row2),
		:global(.row3) {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}
	}
	@media (max-width: 560px) {
		:global(.kpis),
		:global(.kpis.three),
		:global(.kpis.two),
		:global(.row2),
		:global(.row3) {
			grid-template-columns: 1fr;
		}
	}

	/* Sidebar: no white sticky home block, clear active pill */
	:global(aside a.sticky) { position: static !important; background: transparent !important; box-shadow: none !important; font-weight: 500 !important; padding: 0.3rem 0.75rem !important; margin: 0 !important; color: var(--nb-muted, #5b6472) !important; }
	:global(aside a) { text-transform: none !important; border-radius: 8px; padding: 0.3rem 0.75rem !important; font-size: 0.9rem; }
	:global(aside a.text-primary) { background: #e3edfd; color: #1f55c4 !important; font-weight: 600; }
	:global(aside a:hover) { background: #eaf0f6; text-decoration: none !important; }
</style>
