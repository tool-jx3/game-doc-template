// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import starlightAutoSidebar from 'starlight-auto-sidebar';

// ============================================
// 遊戲文件設定
// ============================================
// TODO: 修改以下設定以符合您的遊戲

const SITE_CONFIG = {
	// 網站標題（顯示在導航列）
	title: '遊戲規則文件',
	// 預設語言
	defaultLocale: 'zh-TW',
	localeLabel: '繁體中文',
	// SEO：設為 true 允許搜尋引擎索引
	allowIndexing: false,
};

// ============================================
// Astro 設定（通常不需修改）
// ============================================

export default defineConfig({
	markdown: {
		smartypants: false,
	},
	integrations: [
		starlight({
			title: SITE_CONFIG.title,
			head: [
				// SEO 設定
				{
					tag: 'meta',
					attrs: {
						name: 'robots',
						content: SITE_CONFIG.allowIndexing ? 'index, follow' : 'noindex, nofollow',
					},
				},
				// Starlight 只把上一頁側邊欄的 scrollTop 原封不動貼回來，從來不會
				// 去找當前頁的項目。規則書拆完常有上百個連結、數十個群組且預設全
				// 展開，所以從內文連結、搜尋結果或重新整理進來時，高亮的那一項通常
				// 在視窗外好幾個螢幕的位置。這段補上「不在可視範圍內才置中」。
				{
					tag: 'script',
					content: `(() => {
	const reveal = () => {
		for (const pane of document.querySelectorAll('.sidebar-pane')) {
			const link = pane.querySelector('a[aria-current="page"]');
			if (!link) continue;
			const l = link.getBoundingClientRect();
			const p = pane.getBoundingClientRect();
			// 版面還沒算好，或該項目已經看得到，就不要動它
			if (!p.height || (l.top >= p.top && l.bottom <= p.bottom)) continue;
			// 直接改容器的 scrollTop，不用 scrollIntoView——後者會連整頁一起捲
			pane.scrollTop += l.top - p.top - (p.height - l.height) / 2;
		}
	};
	if (document.readyState === 'loading') {
		document.addEventListener('DOMContentLoaded', reveal);
	} else {
		reveal();
	}
	// 日後若啟用 view transitions 也能沿用
	document.addEventListener('astro:page-load', reveal);
})();`,
				},
			],
			defaultLocale: 'root',
			locales: {
				root: { label: SITE_CONFIG.localeLabel, lang: SITE_CONFIG.defaultLocale },
			},
			// ============================================
			// 側邊欄設定
			// TODO: 根據您的內容結構修改
			// ============================================
			sidebar: [],
			plugins: [starlightAutoSidebar()],
			customCss: ['./src/styles/custom.css'],
		}),
	],
});
