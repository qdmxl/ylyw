selector_to_html = {"a[href=\"#id2\"]": "<h2 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">1.7.1 </span>\u624b\u81c2\u53ef\u4fdd\u8bc1\u6d3b\u52a8\u7a7a\u95f4<a class=\"headerlink\" href=\"#id2\" title=\"Link to this heading\">\uf0c1</a></h2>", "a[href=\"#id1\"]": "<h1 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">1.7 </span>\u5173\u8282\u6d3b\u52a8\u8303\u56f4\u8bf4\u660e<a class=\"headerlink\" href=\"#id1\" title=\"Link to this heading\">\uf0c1</a></h1><h2><span class=\"section-number\">1.7.1 </span>\u624b\u81c2\u53ef\u4fdd\u8bc1\u6d3b\u52a8\u7a7a\u95f4<a class=\"headerlink\" href=\"#id2\" title=\"Link to this heading\">\uf0c1</a></h2>", "a[href=\"#id4\"]": "<h2 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">1.7.3 </span>\u5934\u90e8\u53ef\u4fdd\u8bc1\u6d3b\u52a8\u7a7a\u95f4<a class=\"headerlink\" href=\"#id4\" title=\"Link to this heading\">\uf0c1</a></h2>", "a[href=\"#id5\"]": "<h2 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">1.7.4 </span>\u8170\u90e8\u6d3b\u52a8\u7a7a\u95f4<a class=\"headerlink\" href=\"#id5\" title=\"Link to this heading\">\uf0c1</a></h2>", "a[href=\"#id3\"]": "<h2 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">1.7.2 </span>\u817f\u90e8\u53ef\u4fdd\u8bc1\u6d3b\u52a8\u7a7a\u95f4<a class=\"headerlink\" href=\"#id3\" title=\"Link to this heading\">\uf0c1</a></h2>", "a[href=\"#id6\"]": "<figure class=\"align-center\" id=\"id6\">\n<a class=\"reference internal image-reference\" href=\"../_images/joint_name_and_limit.png\"><img alt=\"\u5173\u8282\u547d\u540d\u793a\u610f\u56fe\" src=\"../_images/joint_name_and_limit.png\" style=\"width: 100%;\"/>\n</a>\n<figcaption>\n<p><span class=\"caption-text\">\u5173\u8282\u547d\u540d\u793a\u610f\u56fe</span><a class=\"headerlink\" href=\"#id6\" title=\"Link to this image\">\uf0c1</a></p>\n</figcaption>\n</figure>"}
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
