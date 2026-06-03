selector_to_html = {"a[href=\"#id2\"]": "<h2 class=\"tippy-header\" style=\"margin-top: 0;\">\u9884\u8bbe\u52a8\u4f5c\u63a7\u5236\u670d\u52a1<a class=\"headerlink\" href=\"#id2\" title=\"Link to this heading\">\uf0c1</a></h2>", "a[href=\"#id1\"]": "<h1 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">5.1.4 </span>\u9884\u8bbe\u52a8\u4f5c\u63a7\u5236<a class=\"headerlink\" href=\"#id1\" title=\"Link to this heading\">\uf0c1</a></h1><p><strong>\u9884\u8bbe\u52a8\u4f5c\u63a7\u5236\u7528\u4e8e\u89e6\u53d1\u5e76\u63a7\u5236\u673a\u5668\u4eba\u6267\u884c\u4e00\u7cfb\u5217\u5e38\u89c1\u7684\u9884\u5b9a\u4e49\u52a8\u4f5c\uff0c\u5982\u6325\u624b\u3001\u63e1\u624b\u3001\u4e3e\u624b\u7b49\u3002\u8be5\u63a5\u53e3\u901a\u8fc7\u7b80\u5355\u7684\u8c03\u7528\uff0c\u80fd\u8fc5\u901f\u63a7\u5236\u673a\u5668\u4eba\u6267\u884c\u7279\u5b9a\u7684\u52a8\u4f5c\uff0c\u9002\u7528\u4e8e\u5e38\u89c1\u7684\u4ea4\u4e92\u573a\u666f\u548c\u4efb\u52a1\u3002</strong></p>", "a[href=\"#id4\"]": "<h2 class=\"tippy-header\" style=\"margin-top: 0;\">\u5b89\u5168\u6ce8\u610f\u4e8b\u9879<a class=\"headerlink\" href=\"#id4\" title=\"Link to this heading\">\uf0c1</a></h2>", "a[href=\"../../example/Python.html#py-preset-motion\"]": "<h2 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">6.1.3 </span>\u8bbe\u7f6e\u673a\u5668\u4eba\u52a8\u4f5c<a class=\"headerlink\" href=\"#py-preset-motion\" title=\"Link to this heading\">\uf0c1</a></h2><p><strong>\u8be5\u793a\u4f8b\u4e2d\u7528\u5230\u4e86preset_motion_client</strong>\uff0c\u8fdb\u5165\u7a33\u5b9a\u7ad9\u7acb\u6a21\u5f0f\u540e\uff0c\u542f\u52a8\u8282\u70b9\u7a0b\u5e8f\uff0c\u8f93\u5165\u76f8\u5e94\u7684\u5b57\u6bb5\u503c\u53ef\u5b9e\u73b0\u5de6\u624b\uff08\u53f3\u624b\uff09\u7684\u63e1\u624b\uff08\u4e3e\u624b\u3001\u6325\u624b\u3001\u98de\u543b\uff09\u52a8\u4f5c\u3002</p><p>\u53ef\u4f9b\u8c03\u7528\u7684\u53c2\u6570\u89c1<a class=\"reference internal\" href=\"../../Interface/control_mod/preset_motion.html#tbl-preset-motion\"><span class=\"std std-ref\">\u9884\u8bbe\u52a8\u4f5c\u8868</span></a></p>", "a[href=\"#id3\"]": "<h2 class=\"tippy-header\" style=\"margin-top: 0;\">\u7f16\u7a0b\u793a\u4f8b<a class=\"headerlink\" href=\"#id3\" title=\"Link to this heading\">\uf0c1</a></h2><p>\u8be6\u7ec6\u7684\u7f16\u7a0b\u793a\u4f8b\u548c\u4ee3\u7801\u8bf4\u660e\u8bf7\u53c2\u8003\uff1a</p>", "a[href=\"../../example/Cpp.html#cpp-preset-motion\"]": "<h2 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">6.2.3 </span>\u8bbe\u7f6e\u673a\u5668\u4eba\u52a8\u4f5c<a class=\"headerlink\" href=\"#cpp-preset-motion\" title=\"Link to this heading\">\uf0c1</a></h2><p><strong>\u8be5\u793a\u4f8b\u4e2d\u7528\u5230\u4e86preset_motion_client</strong>\uff0c\u8fdb\u5165\u7a33\u5b9a\u7ad9\u7acb\u6a21\u5f0f\u540e\uff0c\u542f\u52a8\u8282\u70b9\u7a0b\u5e8f\uff0c\u8f93\u5165\u76f8\u5e94\u7684\u5b57\u6bb5\u503c\u53ef\u5b9e\u73b0\u5de6\u624b\uff08\u53f3\u624b\uff09\u7684\u63e1\u624b\uff08\u4e3e\u624b\u3001\u6325\u624b\u3001\u98de\u543b\uff09\u52a8\u4f5c\u3002</p><p>\u53ef\u4f9b\u8c03\u7528\u7684\u53c2\u6570\u89c1<a class=\"reference internal\" href=\"../../Interface/control_mod/preset_motion.html#tbl-preset-motion\"><span class=\"std std-ref\">\u9884\u8bbe\u52a8\u4f5c\u8868</span></a></p>"}
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
