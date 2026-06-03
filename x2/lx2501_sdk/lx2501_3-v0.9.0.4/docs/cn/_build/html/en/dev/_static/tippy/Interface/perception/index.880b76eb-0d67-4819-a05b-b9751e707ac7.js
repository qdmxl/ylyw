selector_to_html = {"a[href=\"#id1\"]": "<h1 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">5.5 </span>Perception Module (Coming Soon)<a class=\"headerlink\" href=\"#id1\" title=\"Link to this heading\">\uf0c1</a></h1><p><strong>AgiBot X2 SDK Perception Module \u2013 Provides multi-modal perception capabilities</strong></p><p>Key Features</p>", "a[href=\"SLAM.html\"]": "<h1 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">5.5.2 </span>SLAM (Coming Soon)<a class=\"headerlink\" href=\"#slam\" title=\"Link to this heading\">\uf0c1</a></h1>", "a[href=\"vision.html\"]": "<h1 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">5.5.1 </span>Vision (Coming Soon)<a class=\"headerlink\" href=\"#id1\" title=\"Link to this heading\">\uf0c1</a></h1>"}
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
