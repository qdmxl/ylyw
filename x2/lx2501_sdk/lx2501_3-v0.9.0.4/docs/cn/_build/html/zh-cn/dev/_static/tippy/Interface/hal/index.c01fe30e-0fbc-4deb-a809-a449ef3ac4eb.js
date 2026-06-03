selector_to_html = {"a[href=\"pmu.html\"]": "<h1 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">5.4.2 </span>\u7535\u6e90\u7ba1\u7406\u5355\u5143 (PMU)<a class=\"headerlink\" href=\"#pmu\" title=\"Link to this heading\">\uf0c1</a></h1><p><strong>\u7535\u6e90\u7ba1\u7406\u5355\u5143\u63a5\u53e3\u63d0\u4f9b\u4e86\u673a\u5668\u4eba\u7535\u6e90\u7cfb\u7edf\u7684\u76d1\u63a7\u548c\u7ba1\u7406\u80fd\u529b\uff0c\u5305\u62ec\u7535\u6c60\u72b6\u6001\u3001\u7535\u538b\u7535\u6d41\u76d1\u63a7\u7b49\u529f\u80fd\u3002</strong></p>", "a[href=\"sensor.html\"]": "<h1 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">5.4.1 </span>\u4f20\u611f\u5668\u63a5\u53e3<a class=\"headerlink\" href=\"#id1\" title=\"Link to this heading\">\uf0c1</a></h1><p><strong>\u4f20\u611f\u5668\u63a5\u53e3\u63d0\u4f9b\u4e86\u673a\u5668\u4eba\u5404\u79cd\u4f20\u611f\u5668\u7684\u6570\u636e\u83b7\u53d6\u548c\u63a7\u5236\u80fd\u529b\uff0c\u5305\u62ec\u76f8\u673a\u3001IMU\u3001\u6fc0\u5149\u96f7\u8fbe\u3001\u89e6\u6478\u4f20\u611f\u5668\u7b49\u3002</strong></p>", "a[href=\"#id1\"]": "<h1 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">5.4 </span>\u786c\u4ef6\u62bd\u8c61\u6a21\u5757<a class=\"headerlink\" href=\"#id1\" title=\"Link to this heading\">\uf0c1</a></h1><p><strong>\u667a\u5143\u673a\u5668\u4ebaX2 AimDK\u786c\u4ef6\u62bd\u8c61\u6a21\u5757 - \u63d0\u4f9b\u5e95\u5c42\u786c\u4ef6\u63a5\u53e3\u548c\u4f20\u611f\u5668\u6570\u636e\u83b7\u53d6\u80fd\u529b</strong></p><p>\u786c\u4ef6\u62bd\u8c61\u6a21\u5757\u662f\u667a\u5143\u673a\u5668\u4ebaX2 AimDK\u7684\u5e95\u5c42\u7ec4\u4ef6\uff0c\u63d0\u4f9b\u4e86\u5bf9\u673a\u5668\u4eba\u5404\u79cd\u786c\u4ef6\u8bbe\u5907\u7684\u62bd\u8c61\u63a5\u53e3\u3002\u8be5\u6a21\u5757\u9075\u5faaROS2\u6807\u51c6\uff0c\u652f\u6301C++\u548cPython\u4e24\u79cd\u7f16\u7a0b\u8bed\u8a00\uff0c\u4e3a\u5f00\u53d1\u8005\u63d0\u4f9b\u7edf\u4e00\u7684\u786c\u4ef6\u8bbf\u95ee\u63a5\u53e3\u3002</p>"}
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
