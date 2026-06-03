selector_to_html = {"a[href=\"#id2\"]": "<h2 class=\"tippy-header\" style=\"margin-top: 0;\">\u6838\u5fc3\u7279\u6027<a class=\"headerlink\" href=\"#id2\" title=\"Link to this heading\">\uf0c1</a></h2>", "a[href=\"../../example/Cpp.html#cpp-play-lights\"]": "<h2 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">6.2.20 </span>LED\u706f\u5e26\u63a7\u5236<a class=\"headerlink\" href=\"#cpp-play-lights\" title=\"Link to this heading\">\uf0c1</a></h2><p><strong>\u529f\u80fd\u8bf4\u660e</strong>\uff1a\u6f14\u793a\u5982\u4f55\u63a7\u5236\u673a\u5668\u4eba\u7684LED\u706f\u5e26\uff0c\u652f\u6301\u591a\u79cd\u663e\u793a\u6a21\u5f0f\u548c\u81ea\u5b9a\u4e49\u989c\u8272\u3002</p><p><strong>\u6838\u5fc3\u4ee3\u7801</strong>\uff1a</p>", "a[href=\"#id1\"]": "<h1 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">5.2.3 </span>\u706f\u5e26\u63a7\u5236<a class=\"headerlink\" href=\"#id1\" title=\"Link to this heading\">\uf0c1</a></h1><p><strong>\u80f8\u524d\u706f\u5e26\u63a7\u5236\u63a5\u53e3\u63d0\u4f9b\u4e86\u6269\u5c55\u7684\u89c6\u89c9\u4ea4\u4e92\u529f\u80fd\u3002</strong></p>", "a[href=\"#id4\"]": "<h2 class=\"tippy-header\" style=\"margin-top: 0;\">\u7f16\u7a0b\u793a\u4f8b<a class=\"headerlink\" href=\"#id4\" title=\"Link to this heading\">\uf0c1</a></h2><p>\u8be6\u7ec6\u7684\u7f16\u7a0b\u793a\u4f8b\u548c\u4ee3\u7801\u8bf4\u660e\u8bf7\u53c2\u8003\uff1a</p>", "a[href=\"../../example/Python.html#py-play-lights\"]": "<h2 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">6.1.20 </span>LED\u706f\u5e26\u63a7\u5236<a class=\"headerlink\" href=\"#py-play-lights\" title=\"Link to this heading\">\uf0c1</a></h2><p><strong>\u529f\u80fd\u8bf4\u660e</strong>\uff1a\u6f14\u793a\u5982\u4f55\u63a7\u5236\u673a\u5668\u4eba\u7684LED\u706f\u5e26\uff0c\u652f\u6301\u591a\u79cd\u663e\u793a\u6a21\u5f0f\u548c\u81ea\u5b9a\u4e49\u989c\u8272\u3002</p><p><strong>\u6838\u5fc3\u4ee3\u7801</strong>\uff1a</p>", "a[href=\"#id3\"]": "<h2 class=\"tippy-header\" style=\"margin-top: 0;\">\u706f\u5e26\u63a7\u5236\u670d\u52a1<a class=\"headerlink\" href=\"#id3\" title=\"Link to this heading\">\uf0c1</a></h2>"}
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
