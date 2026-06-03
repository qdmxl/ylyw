selector_to_html = {"a[href=\"#id1\"]": "<h1 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">1.8 </span>Coordinate System<a class=\"headerlink\" href=\"#id1\" title=\"Link to this heading\">\uf0c1</a></h1><p>When all joint angles are at their zero positions, the coordinate systems of each robot component are distributed as shown in the figure below. <strong>Red indicates the X-axis, green indicates the Y-axis, and blue indicates the Z-axis</strong>.</p>", "a[href=\"#id2\"]": "<figure class=\"align-center\" id=\"id2\">\n<a class=\"reference internal image-reference\" href=\"../_images/coordinate_system.png\"><img alt=\"\u5750\u6807\u7cfb\u793a\u610f\u56fe\" src=\"../_images/coordinate_system.png\" style=\"width: 80%;\"/>\n</a>\n<figcaption>\n<p><span class=\"caption-text\">Coordinate System Diagram</span><a class=\"headerlink\" href=\"#id2\" title=\"Link to this image\">\uf0c1</a></p>\n</figcaption>\n</figure>"}
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
