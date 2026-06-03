selector_to_html = {"a[href=\"#id2\"]": "<h1 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">4.2 </span>\u5b8c\u6210\u57fa\u7840\u7cfb\u7edf\u914d\u7f6e<a class=\"headerlink\" href=\"#id2\" title=\"Link to this heading\">\uf0c1</a></h1><p>\u4ee5\u53caSDK\u4f8b\u7a0b\u4f9d\u8d56\u5e93:</p>", "a[href=\"#id1\"]": "<h1 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">4.1 </span>\u9605\u8bfb\u7528\u6237\u4f7f\u7528\u6307\u5357\uff0c\u719f\u6089\u76f8\u5173\u672f\u8bed\u53ca\u5b89\u5168\u6ce8\u610f\u4e8b\u9879<a class=\"headerlink\" href=\"#id1\" title=\"Link to this heading\">\uf0c1</a></h1>", "a[href=\"../about_agibot_X2/SDK_interface.html#img-x2-sdk-interface\"]": "<figure class=\"align-left\" id=\"img-x2-sdk-interface\">\n<a class=\"reference internal image-reference\" href=\"../_images/SDK_interface.png\"><img alt=\"\u7075\u7280 X2 Ultra \u65d7\u8230\u7248 \u4e8c\u6b21\u5f00\u53d1\u63a5\u53e3\u5e03\u5c40\u793a\u610f\" src=\"../_images/SDK_interface.png\" style=\"width: 100%;\"/>\n</a>\n<figcaption>\n<p><span class=\"caption-text\">\u7075\u7280 X2 Ultra \u65d7\u8230\u7248 \u4e8c\u6b21\u5f00\u53d1\u63a5\u53e3\u5e03\u5c40\u793a\u610f</span><a class=\"headerlink\" href=\"#img-x2-sdk-interface\" title=\"Link to this image\">\uf0c1</a></p>\n</figcaption>\n</figure>", "a[href=\"#aimdk-build\"]": "<h1 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">4.4 </span>\u73af\u5883\u5b89\u88c5\u548c\u914d\u7f6e<a class=\"headerlink\" href=\"#aimdk-build\" title=\"Link to this heading\">\uf0c1</a></h1><p>\u5c06 SDK \u653e\u5165\u76ee\u6807\u8fd0\u884c\u73af\u5883\u5e76\u89e3\u538b</p>", "a[href=\"#id3\"]": "<h1 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">4.3 </span>\u7f51\u7edc\u8fde\u63a5<a class=\"headerlink\" href=\"#id3\" title=\"Link to this heading\">\uf0c1</a></h1><p>\u7075\u7280 X2 \u65d7\u8230\u7248\u652f\u6301\u591a\u79cd\u7f51\u7edc\u63a5\u5165\u65b9\u5f0f\u8fde\u63a5\u673a\u5668\u4eba\u5185\u7cfb\u7edf\uff1a</p><p><strong>\uff081\uff09\u901a\u8fc7\u673a\u5668\u4eba\u80cc\u90e8\u7684\u6709\u7ebf\u7f51\u53e3\u76f4\u63a5\u8fde\u63a5</strong>\n\u4f7f\u7528\u7f51\u7ebf\u8fde\u63a5<a class=\"reference internal\" href=\"../about_agibot_X2/SDK_interface.html#img-x2-sdk-interface\"><span class=\"std std-ref\">\u4e8c\u6b21\u5f00\u53d1\u7f51\u53e3</span></a>\u4e0e\u4e0a\u4f4d\u673a\u7aef\u53e3\u3002</p>"}
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
