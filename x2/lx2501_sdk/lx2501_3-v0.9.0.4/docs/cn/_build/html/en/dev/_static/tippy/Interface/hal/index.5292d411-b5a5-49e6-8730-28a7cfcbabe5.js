selector_to_html = {"a[href=\"#id1\"]": "<h1 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">5.4 </span>Hardware Abstraction Module<a class=\"headerlink\" href=\"#id1\" title=\"Link to this heading\">\uf0c1</a></h1><p><strong>AgiBot X2 AimDK Hardware Abstraction Module \u2013 Provides Low-Level Hardware Interfaces and Sensor Data Access</strong></p><p>The hardware abstraction module is a foundational component of the AgiBot X2 AimDK, providing abstracted interfaces to the robot\u2019s various hardware devices. It follows the ROS2 standard and supports both C++ and Python, offering developers a unified hardware access interface.</p>", "a[href=\"pmu.html\"]": "<h1 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">5.4.2 </span>Power Management Unit (PMU)<a class=\"headerlink\" href=\"#pmu\" title=\"Link to this heading\">\uf0c1</a></h1><p><strong>The Power Management Unit interface provides monitoring and management of the robot\u2019s power system, including battery status, voltage and current monitoring, and more.</strong></p>", "a[href=\"sensor.html\"]": "<h1 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">5.4.1 </span>Sensor Interfaces<a class=\"headerlink\" href=\"#id1\" title=\"Link to this heading\">\uf0c1</a></h1><p><strong>The sensor interfaces provide data access and control for the robot\u2019s various sensors, including cameras, IMUs, LiDAR, and touch sensors.</strong></p>"}
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
