selector_to_html = {"a[href=\"#x2-ultra\"]": "<h2 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">1.1.1 </span>\u65d7\u8230\u7248\uff08X2 Ultra\uff09<a class=\"headerlink\" href=\"#x2-ultra\" title=\"Link to this heading\">\uf0c1</a></h2>", "a[href=\"#id1\"]": "<h1 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">1.1 </span>\u4ea7\u54c1\u7b80\u4ecb<a class=\"headerlink\" href=\"#id1\" title=\"Link to this heading\">\uf0c1</a></h1><h2><span class=\"section-number\">1.1.1 </span>\u65d7\u8230\u7248\uff08X2 Ultra\uff09<a class=\"headerlink\" href=\"#x2-ultra\" title=\"Link to this heading\">\uf0c1</a></h2>"}
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
