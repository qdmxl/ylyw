selector_to_html = {"a[href=\"#aimdk\"]": "<h1 class=\"tippy-header\" style=\"margin-top: 0;\"><i class=\"fa-regular fa-envelope\"></i> AimDK\u4f7f\u7528\u95ee\u9898\u53cd\u9988<a class=\"headerlink\" href=\"#aimdk\" title=\"Link to this heading\">\uf0c1</a></h1><p>\u60a8\u5bf9AgiBot X2 \u4e8c\u6b21\u5f00\u53d1\u529f\u80fd\u7684\u5b9d\u8d35\u610f\u89c1\u4e0e\u5efa\u8bae, \u8bf7\u901a\u8fc7\u4ee5\u4e0b\u94fe\u63a5\u53cd\u9988\u7ed9\u6211\u4eec: <a class=\"reference external\" href=\"https://agirobot.feishu.cn/share/base/form/shrcnV2IFowlEZimcr6enRL1GFc\"><i class=\"fa fa-pen-to-square\"></i></a></p>"}
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
