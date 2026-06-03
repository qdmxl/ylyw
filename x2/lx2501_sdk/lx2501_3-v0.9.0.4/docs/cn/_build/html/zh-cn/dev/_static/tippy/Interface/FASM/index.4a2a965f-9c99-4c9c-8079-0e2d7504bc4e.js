selector_to_html = {"a[href=\"sudo.html\"]": "<h1 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">5.3.2 </span>\u6743\u9650\u7ba1\u7406 \uff08\u5f85\u4e0a\u7ebf\uff09<a class=\"headerlink\" href=\"#id1\" title=\"Link to this heading\">\uf0c1</a></h1>", "a[href=\"fault.html\"]": "<h1 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">5.3.1 </span>\u6545\u969c\u5904\u7406 \uff08\u5f85\u4e0a\u7ebf\uff09<a class=\"headerlink\" href=\"#id1\" title=\"Link to this heading\">\uf0c1</a></h1>", "a[href=\"#id1\"]": "<h1 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">5.3 </span>\u6545\u969c\u4e0e\u7cfb\u7edf\u7ba1\u7406\u6a21\u5757 (\u5f85\u53d1\u5e03)<a class=\"headerlink\" href=\"#id1\" title=\"Link to this heading\">\uf0c1</a></h1><p><strong>\u667a\u5143\u673a\u5668\u4ebaX2 SDK\u6545\u969c\u4e0e\u7cfb\u7edf\u7ba1\u7406\u6a21\u5757 - \u63d0\u4f9b\u6545\u969c\u8bca\u65ad\u548c\u7cfb\u7edf\u7ba1\u7406\u529f\u80fd</strong></p><p>\u6545\u969c\u4e0e\u7cfb\u7edf\u7ba1\u7406\u6a21\u5757\u662f\u667a\u5143\u673a\u5668\u4ebaX2 SDK\u7684\u91cd\u8981\u7ec4\u4ef6\uff0c\u63d0\u4f9b\u4e86\u673a\u5668\u4eba\u6545\u969c\u8bca\u65ad\u548c\u7cfb\u7edf\u7ba1\u7406\u7684\u80fd\u529b\u3002\u901a\u8fc7\u8fd9\u4e9b\u63a5\u53e3\uff0c\u5f00\u53d1\u8005\u53ef\u4ee5\u53ca\u65f6\u53d1\u73b0\u548c\u5904\u7406\u673a\u5668\u4eba\u6545\u969c\uff0c\u7ba1\u7406\u7cfb\u7edf\u6743\u9650\uff0c\u76d1\u63a7\u7cfb\u7edf\u72b6\u6001\uff0c\u786e\u4fdd\u673a\u5668\u4eba\u7684\u5b89\u5168\u7a33\u5b9a\u8fd0\u884c\u3002</p>"}
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
