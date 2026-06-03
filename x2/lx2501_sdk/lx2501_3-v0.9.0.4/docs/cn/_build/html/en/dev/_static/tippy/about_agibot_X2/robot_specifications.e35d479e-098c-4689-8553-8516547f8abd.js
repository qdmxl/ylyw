selector_to_html = {"a[href=\"#id1\"]": "<h1 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">1.2 </span>Robot Specifications<a class=\"headerlink\" href=\"#id1\" title=\"Link to this heading\">\uf0c1</a></h1><p>The <strong>AgiBot X2 Series</strong> is equipped with a comprehensive set of <strong>hardware and system resources</strong>, including the <strong>mechanical structure</strong>, <strong>sensor systems</strong>, <strong>communication interfaces</strong>, <strong>computing units, and power systems</strong>. With this highly integrated architecture, the AgiBot X2 enables <strong>complex whole-body motion control</strong>, <strong>intelligent perception and environmental interaction</strong>, and supports <strong>advanced secondary development</strong> through <strong>AimDK</strong>.</p>", "a[href=\"#x2\"]": "<h2 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">1.2.1 </span>X2 Series Parameter<a class=\"headerlink\" href=\"#x2\" title=\"Link to this heading\">\uf0c1</a></h2>"}
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
