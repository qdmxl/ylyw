selector_to_html = {"a[href=\"#x2\"]": "<h2 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">1.2.1 </span>X2 \u7cfb\u5217\u53c2\u6570<a class=\"headerlink\" href=\"#x2\" title=\"Link to this heading\">\uf0c1</a></h2>", "a[href=\"#id1\"]": "<h1 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">1.2 </span>\u673a\u5668\u4eba\u5177\u4f53\u53c2\u6570<a class=\"headerlink\" href=\"#id1\" title=\"Link to this heading\">\uf0c1</a></h1><p><strong>AgiBot X2 \u7cfb\u5217</strong> \u5177\u5907\u5b8c\u5584\u7684 <strong>\u786c\u4ef6\u4e0e\u7cfb\u7edf\u8d44\u6e90</strong>\uff0c\u5305\u62ec<strong>\u673a\u68b0\u7ed3\u6784</strong>\u3001<strong>\u4f20\u611f\u5668\u7cfb\u7edf</strong>\u3001<strong>\u901a\u4fe1\u63a5\u53e3</strong>\u3001<strong>\u8ba1\u7b97\u5355\u5143\u4e0e\u7535\u6e90\u7cfb\u7edf</strong>\u3002\u4f9d\u6258\u8fd9\u4e00\u9ad8\u5ea6\u96c6\u6210\u7684\u67b6\u6784\uff0c\u7075\u7280X2\u80fd\u591f\u5b9e\u73b0 <strong>\u590d\u6742\u7684\u5168\u8eab\u8fd0\u52a8\u63a7\u5236</strong>\uff0c<strong>\u667a\u80fd\u611f\u77e5\u4e0e\u73af\u5883\u4ea4\u4e92</strong>\uff0c\u5e76\u901a\u8fc7<strong>AimDK</strong>\u652f\u6301 <strong>\u9ad8\u7ea7\u4e8c\u6b21\u5f00\u53d1</strong>\u3002</p>"}
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
