selector_to_html = {"a[href=\"#id1\"]": "<h1 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">8 </span><i class=\"fa fa-gears\"></i> Temporary Transitional Solutions Statement<a class=\"headerlink\" href=\"#id1\" title=\"Link to this heading\">\uf0c1</a></h1><h2><span class=\"section-number\">8.1 </span>Disable the Built-in Interaction System and Use Your Own Voice System<a class=\"headerlink\" href=\"#agent-only-voice\" title=\"Link to this heading\">\uf0c1</a></h2><p><strong>By default, when the robot is powered on, it automatically enters natural voice interaction mode, and the interaction module occupies the audio input/output streams.</strong> If you need to integrate your own voice system and access the audio streams, you can temporarily disable the built-in interaction module using the steps below. <strong>Future versions will support one-click switching to secondary-development interaction mode to further simplify custom voice system integration.</strong></p>", "a[href=\"#agent-only-voice\"]": "<h2 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">8.1 </span>Disable the Built-in Interaction System and Use Your Own Voice System<a class=\"headerlink\" href=\"#agent-only-voice\" title=\"Link to this heading\">\uf0c1</a></h2><p><strong>By default, when the robot is powered on, it automatically enters natural voice interaction mode, and the interaction module occupies the audio input/output streams.</strong> If you need to integrate your own voice system and access the audio streams, you can temporarily disable the built-in interaction module using the steps below. <strong>Future versions will support one-click switching to secondary-development interaction mode to further simplify custom voice system integration.</strong></p>", "a[href=\"#id3\"]": "<h3 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">8.1.2 </span>Steps to Restore the Built-in Interaction System<a class=\"headerlink\" href=\"#id3\" title=\"Link to this heading\">\uf0c1</a></h3>", "a[href=\"#v0-7-xmcaction\"]": "<h2 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">8.2 </span>Motion State Simplification: Some McAction state codes prior to v0.7.x are no longer supported<a class=\"headerlink\" href=\"#v0-7-xmcaction\" title=\"Link to this heading\">\uf0c1</a></h2>", "a[href=\"../Interface/interactor/voice.html#mic-receiver-vad\"]": "<h2 class=\"tippy-header\" style=\"margin-top: 0;\">MIC Audio Stream Capture Topic<a class=\"headerlink\" href=\"#mic-receiver-vad\" title=\"Link to this heading\">\uf0c1</a></h2><p>Supports receiving VAD (Voice Activity Detection) events on denoised audio and the corresponding audio stream.</p>", "a[href=\"#id2\"]": "<h3 class=\"tippy-header\" style=\"margin-top: 0;\"><span class=\"section-number\">8.1.1 </span>Steps to Temporarily Disable the Built-in Interaction System<a class=\"headerlink\" href=\"#id2\" title=\"Link to this heading\">\uf0c1</a></h3>"}
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
