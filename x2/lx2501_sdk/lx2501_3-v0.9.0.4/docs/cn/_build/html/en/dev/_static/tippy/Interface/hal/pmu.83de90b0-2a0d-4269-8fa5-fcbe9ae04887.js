selector_to_html = {"a[href=\"#id1\"]": "<h2 class=\"tippy-header\" style=\"margin-top: 0;\">Core Features<a class=\"headerlink\" href=\"#id1\" title=\"Link to this heading\">\uf0c1</a></h2><h3>Battery Monitoring<a class=\"headerlink\" href=\"#id2\" title=\"Link to this heading\">\uf0c1</a></h3>", "a[href=\"#id3\"]": "<h3 class=\"tippy-header\" style=\"margin-top: 0;\">Power Management<a class=\"headerlink\" href=\"#id3\" title=\"Link to this heading\">\uf0c1</a></h3>", "a[href=\"#pmu\"]": "<h1 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">5.4.2 </span>Power Management Unit (PMU)<a class=\"headerlink\" href=\"#pmu\" title=\"Link to this heading\">\uf0c1</a></h1><p><strong>The Power Management Unit interface provides monitoring and management of the robot\u2019s power system, including battery status, voltage and current monitoring, and more.</strong></p>", "a[href=\"#id6\"]": "<h2 class=\"tippy-header\" style=\"margin-top: 0;\">Safety Notes<a class=\"headerlink\" href=\"#id6\" title=\"Link to this heading\">\uf0c1</a></h2>", "a[href=\"#id4\"]": "<h3 class=\"tippy-header\" style=\"margin-top: 0;\">System Monitoring<a class=\"headerlink\" href=\"#id4\" title=\"Link to this heading\">\uf0c1</a></h3>", "a[href=\"#id5\"]": "<h2 class=\"tippy-header\" style=\"margin-top: 0;\">Power Management Topic<a class=\"headerlink\" href=\"#id5\" title=\"Link to this heading\">\uf0c1</a></h2>", "a[href=\"#id2\"]": "<h3 class=\"tippy-header\" style=\"margin-top: 0;\">Battery Monitoring<a class=\"headerlink\" href=\"#id2\" title=\"Link to this heading\">\uf0c1</a></h3>"}
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
