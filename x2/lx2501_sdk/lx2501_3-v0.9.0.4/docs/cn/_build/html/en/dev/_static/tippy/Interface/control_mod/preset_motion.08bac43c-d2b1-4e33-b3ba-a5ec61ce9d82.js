selector_to_html = {"a[href=\"#id1\"]": "<h1 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">5.1.4 </span>Preset Motion Control<a class=\"headerlink\" href=\"#id1\" title=\"Link to this heading\">\uf0c1</a></h1><p><strong>Preset motion control allows the robot to execute predefined actions such as waving, handshaking, raising an arm, etc. With a simple service call, the robot can quickly perform specific actions, making this interface ideal for common interaction scenarios.</strong></p>", "a[href=\"#id3\"]": "<h2 class=\"tippy-header\" style=\"margin-top: 0;\">Programming Examples<a class=\"headerlink\" href=\"#id3\" title=\"Link to this heading\">\uf0c1</a></h2><p>For detailed programming examples and code explanations, see:</p>", "a[href=\"#id4\"]": "<h2 class=\"tippy-header\" style=\"margin-top: 0;\">Safety Notes<a class=\"headerlink\" href=\"#id4\" title=\"Link to this heading\">\uf0c1</a></h2>", "a[href=\"../../example/Python.html#py-preset-motion\"]": "<h2 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">6.1.3 </span>Set robot action<a class=\"headerlink\" href=\"#py-preset-motion\" title=\"Link to this heading\">\uf0c1</a></h2><p><strong>This example uses <code class=\"docutils literal notranslate\"><span class=\"pre\">preset_motion_client</span></code></strong>; after switching to Stable Stand Mode and starting the node, enter the corresponding field values to perform preset actions with the left (or right) hand such as handshake, raise hand, wave, or air kiss.</p><p>Available parameters are listed in the <a class=\"reference internal\" href=\"../../Interface/control_mod/preset_motion.html#tbl-preset-motion\"><span class=\"std std-ref\">preset motions table</span></a></p>", "a[href=\"../../example/Cpp.html#cpp-preset-motion\"]": "<h2 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">6.2.3 </span>Set Robot Motion<a class=\"headerlink\" href=\"#cpp-preset-motion\" title=\"Link to this heading\">\uf0c1</a></h2><p><strong>This example uses <code class=\"docutils literal notranslate\"><span class=\"pre\">preset_motion_client</span></code></strong>; after switching to Stable Stand Mode and starting the node, enter the corresponding field values to perform preset actions with the left (or right) hand such as handshake, raise hand, wave, or air kiss.</p><p>Available parameters can be found in the <a class=\"reference internal\" href=\"../../Interface/control_mod/preset_motion.html#tbl-preset-motion\"><span class=\"std std-ref\">Preset Motion Table</span></a></p>", "a[href=\"#id2\"]": "<h2 class=\"tippy-header\" style=\"margin-top: 0;\">Preset Motion Control Service<a class=\"headerlink\" href=\"#id2\" title=\"Link to this heading\">\uf0c1</a></h2>"}
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
