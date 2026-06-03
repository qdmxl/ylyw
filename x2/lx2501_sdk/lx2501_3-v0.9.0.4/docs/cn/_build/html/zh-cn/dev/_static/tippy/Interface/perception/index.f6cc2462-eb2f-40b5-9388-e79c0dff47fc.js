selector_to_html = {"a[href=\"SLAM.html\"]": "<h1 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">5.5.2 </span>SLAM (\u5f85\u53d1\u5e03)<a class=\"headerlink\" href=\"#slam\" title=\"Link to this heading\">\uf0c1</a></h1>", "a[href=\"vision.html\"]": "<h1 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">5.5.1 </span>\u89c6\u89c9(\u5f85\u53d1\u5e03)<a class=\"headerlink\" href=\"#id1\" title=\"Link to this heading\">\uf0c1</a></h1>", "a[href=\"#id1\"]": "<h1 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">5.5 </span>\u611f\u77e5\u6a21\u5757\uff08\u5f85\u5f00\u653e\uff09<a class=\"headerlink\" href=\"#id1\" title=\"Link to this heading\">\uf0c1</a></h1><p><strong>\u667a\u5143\u673a\u5668\u4ebaX2 SDK\u611f\u77e5\u6a21\u5757 - \u63d0\u4f9b\u591a\u6a21\u6001\u611f\u77e5\u80fd\u529b</strong></p><p><strong>\u6838\u5fc3\u529f\u80fd</strong></p>"}
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
