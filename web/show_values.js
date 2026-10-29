import { app } from "../../scripts/app.js";
import { ComfyWidgets } from "../../scripts/widgets.js";

app.registerExtension({
    name: "SHR.ShowValues",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "SHRShowValues") return;
        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = onNodeCreated?.apply(this, arguments);
            const widget = ComfyWidgets.STRING(this, "display", ["STRING", { multiline: true }], app).widget;
            widget.inputEl.readOnly = true;
            widget.inputEl.setAttribute("aria-label", "SHR Show Values output");
            widget.options.serialize = false;
            this.shrValuesDisplay = widget;
            this.setSize([Math.max(this.size[0], 340), Math.max(this.size[1], 260)]);
            return result;
        };
        const onExecuted = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function (message) {
            onExecuted?.apply(this, arguments);
            if (this.shrValuesDisplay) {
                this.shrValuesDisplay.value = (message.text ?? []).join("\n");
                this.setDirtyCanvas(true, true);
            }
        };
    },
});
