selector_to_html = {"a[href=\"#id3\"]": "<h2 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">1.3.2 </span>\u5f00\u53d1\u8ba1\u7b97\u5355\u5143\u5177\u4f53\u53c2\u6570<a class=\"headerlink\" href=\"#id3\" title=\"Link to this heading\">\uf0c1</a></h2>", "a[href=\"#id2\"]": "<h2 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">1.3.1 </span>\u6807\u914d\u8ba1\u7b97\u5355\u5143<a class=\"headerlink\" href=\"#id2\" title=\"Link to this heading\">\uf0c1</a></h2>", "a[href=\"#id1\"]": "<h1 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">1.3 </span>\u8ba1\u7b97\u5355\u5143<a class=\"headerlink\" href=\"#id1\" title=\"Link to this heading\">\uf0c1</a></h1><p>\u7075\u7280 X2\u65d7\u8230\u7248\u5219\u6807\u914d\u4e00\u5957\u8fd0\u63a7\u8ba1\u7b97\u5355\u5143\uff0c\u4e00\u5957\u4ea4\u4e92\u8ba1\u7b97\u5355\u5143\u4ee5\u53ca\u4e00\u5957\u5f00\u53d1\u8ba1\u7b97\u5355\u5143\uff0c\u4e3a\u590d\u6742\u4efb\u52a1\u4e0e\u9ad8\u7ea7\u5e94\u7528\u63d0\u4f9b\u66f4\u5f3a\u7684\u8ba1\u7b97\u80fd\u529b\u4e0e\u7075\u6d3b\u6027\u3002</p>"}
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
