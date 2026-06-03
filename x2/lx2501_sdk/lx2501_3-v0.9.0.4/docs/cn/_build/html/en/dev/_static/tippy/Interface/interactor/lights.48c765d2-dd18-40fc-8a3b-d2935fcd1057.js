selector_to_html = {"a[href=\"#id1\"]": "<h1 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">5.2.3 </span>LED Strip Control<a class=\"headerlink\" href=\"#id1\" title=\"Link to this heading\">\uf0c1</a></h1><p><strong>The chest LED strip control interface provides enhanced visual interaction capabilities.</strong></p>", "a[href=\"#id3\"]": "<h2 class=\"tippy-header\" style=\"margin-top: 0;\">LED Strip Control Service<a class=\"headerlink\" href=\"#id3\" title=\"Link to this heading\">\uf0c1</a></h2>", "a[href=\"../../example/Python.html#py-play-lights\"]": "<h2 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">6.1.20 </span>LED light strip control<a class=\"headerlink\" href=\"#py-play-lights\" title=\"Link to this heading\">\uf0c1</a></h2><p><strong>Function description</strong>: Demonstrates how to control the robot\u2019s LED light strip, supporting multiple display modes and custom colors.</p><p><strong>Core code:</strong></p>", "a[href=\"#id4\"]": "<h2 class=\"tippy-header\" style=\"margin-top: 0;\">Programming Examples<a class=\"headerlink\" href=\"#id4\" title=\"Link to this heading\">\uf0c1</a></h2><p>For detailed programming samples and explanations, refer to:</p>", "a[href=\"../../example/Cpp.html#cpp-play-lights\"]": "<h2 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">6.2.20 </span>LED Strip Control<a class=\"headerlink\" href=\"#cpp-play-lights\" title=\"Link to this heading\">\uf0c1</a></h2><p><strong>Function Description</strong>: Demonstrates how to control the robot\u2019s LED strip, supporting multiple display modes and customizable colors.</p><p><strong>Core Code</strong>:</p>", "a[href=\"#id2\"]": "<h2 class=\"tippy-header\" style=\"margin-top: 0;\">Key Features<a class=\"headerlink\" href=\"#id2\" title=\"Link to this heading\">\uf0c1</a></h2>"}
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
