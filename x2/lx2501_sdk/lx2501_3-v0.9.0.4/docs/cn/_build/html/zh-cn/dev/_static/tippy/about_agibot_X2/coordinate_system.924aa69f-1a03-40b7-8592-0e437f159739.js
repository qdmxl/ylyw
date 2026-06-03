selector_to_html = {"a[href=\"#id2\"]": "<figure class=\"align-center\" id=\"id2\">\n<a class=\"reference internal image-reference\" href=\"../_images/coordinate_system.png\"><img alt=\"\u5750\u6807\u7cfb\u793a\u610f\u56fe\" src=\"../_images/coordinate_system.png\" style=\"width: 80%;\"/>\n</a>\n<figcaption>\n<p><span class=\"caption-text\">\u5750\u6807\u7cfb\u793a\u610f\u56fe</span><a class=\"headerlink\" href=\"#id2\" title=\"Link to this image\">\uf0c1</a></p>\n</figcaption>\n</figure>", "a[href=\"#id1\"]": "<h1 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">1.8 </span>\u5750\u6807\u7cfb<a class=\"headerlink\" href=\"#id1\" title=\"Link to this heading\">\uf0c1</a></h1><p>\u5f53\u5404\u5173\u8282\u89d2\u5ea6\u5747\u5904\u4e8e\u96f6\u4f4d\u65f6\uff0c\u673a\u5668\u4eba\u5404\u90e8\u4ef6\u7684\u5750\u6807\u7cfb\u5206\u5e03\u5982\u4e0b\u56fe\u6240\u793a\u3002\u5176\u4e2d\uff0c<strong>\u7ea2\u8272\u8868\u793a X \u8f74\uff0c\u7eff\u8272\u8868\u793a Y \u8f74\uff0c\u84dd\u8272\u8868\u793a Z \u8f74</strong>\u3002</p>"}
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
