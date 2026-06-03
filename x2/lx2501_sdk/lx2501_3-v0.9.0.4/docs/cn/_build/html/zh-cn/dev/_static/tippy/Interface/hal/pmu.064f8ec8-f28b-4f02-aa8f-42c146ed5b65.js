selector_to_html = {"a[href=\"#id2\"]": "<h3 class=\"tippy-header\" style=\"margin-top: 0;\">\u7535\u6c60\u76d1\u63a7<a class=\"headerlink\" href=\"#id2\" title=\"Link to this heading\">\uf0c1</a></h3>", "a[href=\"#id1\"]": "<h2 class=\"tippy-header\" style=\"margin-top: 0;\">\u6838\u5fc3\u529f\u80fd<a class=\"headerlink\" href=\"#id1\" title=\"Link to this heading\">\uf0c1</a></h2><h3>\u7535\u6c60\u76d1\u63a7<a class=\"headerlink\" href=\"#id2\" title=\"Link to this heading\">\uf0c1</a></h3>", "a[href=\"#id4\"]": "<h3 class=\"tippy-header\" style=\"margin-top: 0;\">\u7cfb\u7edf\u76d1\u63a7<a class=\"headerlink\" href=\"#id4\" title=\"Link to this heading\">\uf0c1</a></h3>", "a[href=\"#id6\"]": "<h2 class=\"tippy-header\" style=\"margin-top: 0;\">\u5b89\u5168\u6ce8\u610f\u4e8b\u9879<a class=\"headerlink\" href=\"#id6\" title=\"Link to this heading\">\uf0c1</a></h2>", "a[href=\"#id5\"]": "<h2 class=\"tippy-header\" style=\"margin-top: 0;\">\u7535\u6e90\u7ba1\u7406\u8bdd\u9898<a class=\"headerlink\" href=\"#id5\" title=\"Link to this heading\">\uf0c1</a></h2>", "a[href=\"#id3\"]": "<h3 class=\"tippy-header\" style=\"margin-top: 0;\">\u7535\u6e90\u7ba1\u7406<a class=\"headerlink\" href=\"#id3\" title=\"Link to this heading\">\uf0c1</a></h3>", "a[href=\"#pmu\"]": "<h1 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">5.4.2 </span>\u7535\u6e90\u7ba1\u7406\u5355\u5143 (PMU)<a class=\"headerlink\" href=\"#pmu\" title=\"Link to this heading\">\uf0c1</a></h1><p><strong>\u7535\u6e90\u7ba1\u7406\u5355\u5143\u63a5\u53e3\u63d0\u4f9b\u4e86\u673a\u5668\u4eba\u7535\u6e90\u7cfb\u7edf\u7684\u76d1\u63a7\u548c\u7ba1\u7406\u80fd\u529b\uff0c\u5305\u62ec\u7535\u6c60\u72b6\u6001\u3001\u7535\u538b\u7535\u6d41\u76d1\u63a7\u7b49\u529f\u80fd\u3002</strong></p>"}
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
