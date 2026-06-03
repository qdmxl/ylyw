selector_to_html = {"a[href=\"#id1\"]": "<h1 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">5.2 </span>Interaction Module<a class=\"headerlink\" href=\"#id1\" title=\"Link to this heading\">\uf0c1</a></h1><p><strong>AgiBot X2 AimDK Interaction Module \u2013 providing rich human\u2013robot interaction interfaces</strong></p><p><strong>Core Features</strong></p>", "a[href=\"voice.html\"]": "<h1 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">5.2.1 </span>Voice Control<a class=\"headerlink\" href=\"#id1\" title=\"Link to this heading\">\uf0c1</a></h1><p><strong>The voice control interface provides a complete set of voice interaction capabilities, including speech synthesis, speech recognition, audio noise reduction, audio playback, and volume control.</strong></p>", "a[href=\"screen.html\"]": "<h1 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">5.2.2 </span>Screen Control<a class=\"headerlink\" href=\"#id1\" title=\"Link to this heading\">\uf0c1</a></h1><p><strong>The screen control interface provides full display control capabilities, including emoji playback, video playback, and more. It enables developers to implement rich visual interaction features for the robot.</strong></p>", "a[href=\"lights.html\"]": "<h1 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">5.2.3 </span>LED Strip Control<a class=\"headerlink\" href=\"#id1\" title=\"Link to this heading\">\uf0c1</a></h1><p><strong>The chest LED strip control interface provides enhanced visual interaction capabilities.</strong></p>"}
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
