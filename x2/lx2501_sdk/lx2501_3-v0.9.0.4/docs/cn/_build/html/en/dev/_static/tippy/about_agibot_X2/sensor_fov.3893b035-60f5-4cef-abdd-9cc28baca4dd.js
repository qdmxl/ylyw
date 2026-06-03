selector_to_html = {"a[href=\"#id1\"]": "<h2 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">1.6.1 </span>Sensor Capabilities &amp; FOV Diagram<a class=\"headerlink\" href=\"#id1\" title=\"Link to this heading\">\uf0c1</a></h2>", "a[href=\"#id3\"]": "<h3 class=\"tippy-header\" style=\"margin-top: 0;\">LiDAR<a class=\"headerlink\" href=\"#id3\" title=\"Link to this heading\">\uf0c1</a></h3>", "a[href=\"#rgbd\"]": "<h3 class=\"tippy-header\" style=\"margin-top: 0;\">RGB-D Camera<a class=\"headerlink\" href=\"#rgbd\" title=\"Link to this heading\">\uf0c1</a></h3>", "a[href=\"#id6\"]": "<h3 class=\"tippy-header\" style=\"margin-top: 0;\">Touch Sensor<a class=\"headerlink\" href=\"#id6\" title=\"Link to this heading\">\uf0c1</a></h3>", "a[href=\"#id4\"]": "<h3 class=\"tippy-header\" style=\"margin-top: 0;\">Front Interaction RGB Camera<a class=\"headerlink\" href=\"#id4\" title=\"Link to this heading\">\uf0c1</a></h3>", "a[href=\"#id5\"]": "<h3 class=\"tippy-header\" style=\"margin-top: 0;\">Rear RGB Camera<a class=\"headerlink\" href=\"#id5\" title=\"Link to this heading\">\uf0c1</a></h3>", "a[href=\"#rgb\"]": "<h3 class=\"tippy-header\" style=\"margin-top: 0;\">Front Stereo RGB Camera<a class=\"headerlink\" href=\"#rgb\" title=\"Link to this heading\">\uf0c1</a></h3>", "a[href=\"#x2\"]": "<h1 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">1.6 </span>AgiBot X2 Sensor Overview<a class=\"headerlink\" href=\"#x2\" title=\"Link to this heading\">\uf0c1</a></h1><h2><span class=\"section-number\">1.6.1 </span>Sensor Capabilities &amp; FOV Diagram<a class=\"headerlink\" href=\"#id1\" title=\"Link to this heading\">\uf0c1</a></h2>", "a[href=\"#imu\"]": "<h3 class=\"tippy-header\" style=\"margin-top: 0;\">Standalone Inertial Sensor (IMU)<a class=\"headerlink\" href=\"#imu\" title=\"Link to this heading\">\uf0c1</a></h3>", "a[href=\"#id2\"]": "<h2 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">1.6.2 </span>Sensor Specifications<a class=\"headerlink\" href=\"#id2\" title=\"Link to this heading\">\uf0c1</a></h2><h3>LiDAR<a class=\"headerlink\" href=\"#id3\" title=\"Link to this heading\">\uf0c1</a></h3>"}
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
