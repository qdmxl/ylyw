selector_to_html = {"a[href=\"#aimdk-run\"]": "<h1 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">4.5 </span>\u8fd0\u884c\u4e00\u4e2a\u4ee3\u7801\u793a\u4f8b<a class=\"headerlink\" href=\"#aimdk-run\" title=\"Link to this heading\">\uf0c1</a></h1><h2><span class=\"section-number\">4.5.1 </span>\u83b7\u53d6\u673a\u5668\u4eba\u7684\u5f53\u524d\u72b6\u6001<a class=\"headerlink\" href=\"#id1\" title=\"Link to this heading\">\uf0c1</a></h2><p><strong>\u8f93\u51fa\u793a\u4f8b</strong></p><p>\u5982\u679c\u4f60\u770b\u5230\u5982\u4e0b\u8f93\u51fa\uff0c\u8bf4\u660e\u4f60\u5df2\u6210\u529f\u4e0e\u673a\u5668\u4eba\u5efa\u7acb\u901a\u4fe1\uff0c\u5e76\u83b7\u53d6\u5230\u4e86\u673a\u5668\u4eba\u7684\u5f53\u524d\u8fd0\u52a8\u6a21\u5f0f\u3002</p>", "a[href=\"#id2\"]": "<h2 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">4.5.2 </span>\u8ba9\u673a\u5668\u4eba\u6325\u624b<a class=\"headerlink\" href=\"#id2\" title=\"Link to this heading\">\uf0c1</a></h2><p>\u63a7\u5236\u673a\u5668\u4eba\u5207\u6362\u81f3 <span class=\"highlight-target\">\u7a33\u5b9a\u7ad9\u7acb(\u529b\u63a7\u7ad9\u7acb)\u6a21\u5f0f</span>, \u53c2\u8003\u72b6\u6001\u6d41\u8f6c\u56fe\u5b8c\u6210</p>", "a[href=\"#id1\"]": "<h2 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">4.5.1 </span>\u83b7\u53d6\u673a\u5668\u4eba\u7684\u5f53\u524d\u72b6\u6001<a class=\"headerlink\" href=\"#id1\" title=\"Link to this heading\">\uf0c1</a></h2><p><strong>\u8f93\u51fa\u793a\u4f8b</strong></p><p>\u5982\u679c\u4f60\u770b\u5230\u5982\u4e0b\u8f93\u51fa\uff0c\u8bf4\u660e\u4f60\u5df2\u6210\u529f\u4e0e\u673a\u5668\u4eba\u5efa\u7acb\u901a\u4fe1\uff0c\u5e76\u83b7\u53d6\u5230\u4e86\u673a\u5668\u4eba\u7684\u5f53\u524d\u8fd0\u52a8\u6a21\u5f0f\u3002</p>"}
skip_classes = ["headerlink", "sd-stretched-link"]

window.onload = function () {
    for (const [select, tip_html] of Object.entries(selector_to_html)) {
        const links = document.querySelectorAll(` ${select}`);
        for (const link of links) {
            if (skip_classes.some(c => link.classList.contains(c))) {
                continue;
            }

            tippy(link, {
                content: tip_html,
                allowHTML: true,
                arrow: true,
                placement: 'auto-start', maxWidth: 500, interactive: false, theme: 'material', duration: [300, 200], delay: [200, 100],

            });
        };
    };
    console.log("tippy tips loaded!");
};
