selector_to_html = {"a[href=\"#id2\"]": "<h2 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">1.6.2 </span>\u4f20\u611f\u5668\u5177\u4f53\u53c2\u6570<a class=\"headerlink\" href=\"#id2\" title=\"Link to this heading\">\uf0c1</a></h2><h3>\u6fc0\u5149\u96f7\u8fbe<a class=\"headerlink\" href=\"#id3\" title=\"Link to this heading\">\uf0c1</a></h3>", "a[href=\"#imu\"]": "<h3 class=\"tippy-header\" style=\"margin-top: 0;\">\u72ec\u7acb\u60ef\u6027\u4f20\u611f\u5668\uff08IMU\uff09<a class=\"headerlink\" href=\"#imu\" title=\"Link to this heading\">\uf0c1</a></h3>", "a[href=\"#id1\"]": "<h2 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">1.6.1 </span>\u4f20\u611f\u5668\u80fd\u529b\u53ca\u89c6\u573a\u89d2\u793a\u610f\u56fe<a class=\"headerlink\" href=\"#id1\" title=\"Link to this heading\">\uf0c1</a></h2>", "a[href=\"#id4\"]": "<h3 class=\"tippy-header\" style=\"margin-top: 0;\">\u524d\u89c6\u4ea4\u4e92RGB\u6444\u50cf\u5934<a class=\"headerlink\" href=\"#id4\" title=\"Link to this heading\">\uf0c1</a></h3>", "a[href=\"#rgbd\"]": "<h3 class=\"tippy-header\" style=\"margin-top: 0;\">RGBD\u6444\u50cf\u5934<a class=\"headerlink\" href=\"#rgbd\" title=\"Link to this heading\">\uf0c1</a></h3>", "a[href=\"#x2\"]": "<h1 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">1.6 </span>\u7075\u7280X2 \u4f20\u611f\u5668\u8bf4\u660e<a class=\"headerlink\" href=\"#x2\" title=\"Link to this heading\">\uf0c1</a></h1><h2><span class=\"section-number\">1.6.1 </span>\u4f20\u611f\u5668\u80fd\u529b\u53ca\u89c6\u573a\u89d2\u793a\u610f\u56fe<a class=\"headerlink\" href=\"#id1\" title=\"Link to this heading\">\uf0c1</a></h2>", "a[href=\"#id5\"]": "<h3 class=\"tippy-header\" style=\"margin-top: 0;\">\u540e\u89c6RGB\u6444\u50cf\u5934<a class=\"headerlink\" href=\"#id5\" title=\"Link to this heading\">\uf0c1</a></h3>", "a[href=\"#id3\"]": "<h3 class=\"tippy-header\" style=\"margin-top: 0;\">\u6fc0\u5149\u96f7\u8fbe<a class=\"headerlink\" href=\"#id3\" title=\"Link to this heading\">\uf0c1</a></h3>", "a[href=\"#rgb\"]": "<h3 class=\"tippy-header\" style=\"margin-top: 0;\">\u524d\u89c6\u53cc\u76eeRGB\u6444\u50cf\u5934<a class=\"headerlink\" href=\"#rgb\" title=\"Link to this heading\">\uf0c1</a></h3>", "a[href=\"#id6\"]": "<h3 class=\"tippy-header\" style=\"margin-top: 0;\">\u89e6\u6478\u4f20\u611f\u5668<a class=\"headerlink\" href=\"#id6\" title=\"Link to this heading\">\uf0c1</a></h3>"}
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
