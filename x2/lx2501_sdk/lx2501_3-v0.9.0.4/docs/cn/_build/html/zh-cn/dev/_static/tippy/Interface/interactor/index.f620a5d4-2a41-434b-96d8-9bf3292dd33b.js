selector_to_html = {"a[href=\"lights.html\"]": "<h1 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">5.2.3 </span>\u706f\u5e26\u63a7\u5236<a class=\"headerlink\" href=\"#id1\" title=\"Link to this heading\">\uf0c1</a></h1><p><strong>\u80f8\u524d\u706f\u5e26\u63a7\u5236\u63a5\u53e3\u63d0\u4f9b\u4e86\u6269\u5c55\u7684\u89c6\u89c9\u4ea4\u4e92\u529f\u80fd\u3002</strong></p>", "a[href=\"voice.html\"]": "<h1 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">5.2.1 </span>\u8bed\u97f3\u63a7\u5236<a class=\"headerlink\" href=\"#id1\" title=\"Link to this heading\">\uf0c1</a></h1><p><strong>\u8bed\u97f3\u63a7\u5236\u63a5\u53e3\u63d0\u4f9b\u4e86\u5b8c\u6574\u7684\u8bed\u97f3\u4ea4\u4e92\u80fd\u529b\uff0c\u5305\u62ec\u8bed\u97f3\u5408\u6210\u3001\u8bed\u97f3\u8bc6\u522b\u3001\u97f3\u9891\u964d\u566a\u3001\u97f3\u9891\u64ad\u653e\u548c\u97f3\u91cf\u63a7\u5236\u7b49\u529f\u80fd\u3002</strong></p>", "a[href=\"screen.html\"]": "<h1 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">5.2.2 </span>\u5c4f\u5e55\u63a7\u5236<a class=\"headerlink\" href=\"#id1\" title=\"Link to this heading\">\uf0c1</a></h1><p><strong>\u5c4f\u5e55\u63a7\u5236\u63a5\u53e3\u63d0\u4f9b\u4e86\u5b8c\u6574\u7684\u663e\u793a\u63a7\u5236\u80fd\u529b\uff0c\u5305\u62ec\u8868\u60c5\u63a7\u5236\u3001\u89c6\u9891\u64ad\u653e\u7b49\u529f\u80fd\u3002\u901a\u8fc7\u8be5\u63a5\u53e3\uff0c\u5f00\u53d1\u8005\u53ef\u4ee5\u5b9e\u73b0\u673a\u5668\u4eba\u7684\u89c6\u89c9\u4ea4\u4e92\u80fd\u529b\u3002</strong></p>", "a[href=\"#id1\"]": "<h1 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">5.2 </span>\u4ea4\u4e92\u6a21\u5757<a class=\"headerlink\" href=\"#id1\" title=\"Link to this heading\">\uf0c1</a></h1><p><strong>\u667a\u5143\u673a\u5668\u4ebaX2 AimDK\u4ea4\u4e92\u6a21\u5757 - \u63d0\u4f9b\u4e30\u5bcc\u7684\u4eba\u673a\u4ea4\u4e92\u63a5\u53e3</strong></p><p><strong>\u6838\u5fc3\u529f\u80fd</strong></p>"}
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
