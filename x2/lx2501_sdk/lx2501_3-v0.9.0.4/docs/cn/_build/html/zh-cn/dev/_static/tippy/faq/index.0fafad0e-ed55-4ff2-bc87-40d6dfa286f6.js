selector_to_html = {"a[href=\"../quick_start/prerequisites.html#aimdk-build\"]": "<h1 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">4.4 </span>\u73af\u5883\u5b89\u88c5\u548c\u914d\u7f6e<a class=\"headerlink\" href=\"#aimdk-build\" title=\"Link to this heading\">\uf0c1</a></h1><p>\u5c06 SDK \u653e\u5165\u76ee\u6807\u8fd0\u884c\u73af\u5883\u5e76\u89e3\u538b</p>", "a[href=\"#faq\"]": "<h1 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">7 </span><i class=\"fa-regular fa-circle-question\"></i> FAQ<a class=\"headerlink\" href=\"#faq\" title=\"Link to this heading\">\uf0c1</a></h1><p><strong>Q: \u8fd0\u884c\u4f8b\u7a0b\u62a5\u9519\"Package \u2018examples\u2019 not found\"</strong></p>", "a[href=\"../quick_start/run_example.html#aimdk-run\"]": "<h1 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">4.5 </span>\u8fd0\u884c\u4e00\u4e2a\u4ee3\u7801\u793a\u4f8b<a class=\"headerlink\" href=\"#aimdk-run\" title=\"Link to this heading\">\uf0c1</a></h1><h2><span class=\"section-number\">4.5.1 </span>\u83b7\u53d6\u673a\u5668\u4eba\u7684\u5f53\u524d\u72b6\u6001<a class=\"headerlink\" href=\"#id1\" title=\"Link to this heading\">\uf0c1</a></h2><p><strong>\u8f93\u51fa\u793a\u4f8b</strong></p><p>\u5982\u679c\u4f60\u770b\u5230\u5982\u4e0b\u8f93\u51fa\uff0c\u8bf4\u660e\u4f60\u5df2\u6210\u529f\u4e0e\u673a\u5668\u4eba\u5efa\u7acb\u901a\u4fe1\uff0c\u5e76\u83b7\u53d6\u5230\u4e86\u673a\u5668\u4eba\u7684\u5f53\u524d\u8fd0\u52a8\u6a21\u5f0f\u3002</p>"}
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
