selector_to_html = {"a[href=\"#faq\"]": "<h1 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">7 </span><i class=\"fa-regular fa-circle-question\"></i> FAQ<a class=\"headerlink\" href=\"#faq\" title=\"Link to this heading\">\uf0c1</a></h1><p><strong>Q: Running the example reports: \u201cPackage \u2018examples\u2019 not found\u201d</strong></p>", "a[href=\"../quick_start/run_example.html#aimdk-run\"]": "<h1 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">4.5 </span>Run an Example Program<a class=\"headerlink\" href=\"#aimdk-run\" title=\"Link to this heading\">\uf0c1</a></h1><h2><span class=\"section-number\">4.5.1 </span>Get the Robot\u2019s Current State<a class=\"headerlink\" href=\"#id1\" title=\"Link to this heading\">\uf0c1</a></h2><p><strong>Sample Output</strong></p><p>If you see the following output, you have successfully connected to the robot and retrieved its current Locomotion Mode.</p>", "a[href=\"../quick_start/prerequisites.html#aimdk-build\"]": "<h1 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">4.4 </span>Environment installation and configuration<a class=\"headerlink\" href=\"#aimdk-build\" title=\"Link to this heading\">\uf0c1</a></h1><p>Place the SDK into the target environment and extract it.</p>"}
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
