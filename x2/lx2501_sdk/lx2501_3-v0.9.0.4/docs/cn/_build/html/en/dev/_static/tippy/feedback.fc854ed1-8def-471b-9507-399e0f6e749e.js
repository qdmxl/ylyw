selector_to_html = {"a[href=\"#aimdk\"]": "<h1 class=\"tippy-header\" style=\"margin-top: 0;\"><i class=\"fa-regular fa-envelope\"></i> AimDK Feedback<a class=\"headerlink\" href=\"#aimdk\" title=\"Link to this heading\">\uf0c1</a></h1><p>If you have any valuable feedback or suggestions regarding the AgiBot X2 secondary development features, please share them with us using the following link: <a class=\"reference external\" href=\"https://agirobot.feishu.cn/share/base/form/shrcnV2IFowlEZimcr6enRL1GFc\"><i class=\"fa fa-pen-to-square\"></i></a></p>"}
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
