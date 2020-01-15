import sgtk

import hou


HookBaseClass = sgtk.get_hook_baseclass()


class BaseCacheNodeHandler(HookBaseClass):

    SGTK_SINGLE_FRAME = "sgtk_single_frame"

    def _is_single_frame(self, node):
        sgtk_single_frame = node.parm(self.SGTK_SINGLE_FRAME)
        if sgtk_single_frame:
            return bool(sgtk_single_frame.eval())
        else:
            return True

    def get_work_template(self, node):
        if self._is_single_frame(node):
            return self._work_template
        else:
            return self._get_template("seq_work_template")

    def get_publish_template(self, node):
        if self._is_single_frame(node):
            return self._publish_template
        else:
            return self._get_template("seq_publish_template")

    def _build_single_file_parm(self, default):
        sgtk_single_frame = hou.ToggleParmTemplate(
            self.SGTK_SINGLE_FRAME,
            "Single Frame",
            default_value=default,
            script_callback=self.generate_callback_script_str("refresh_file_path"),
            script_callback_language=hou.scriptLanguage.Python
        )
        sgtk_single_frame.setConditional(
            hou.parmCondType.DisableWhen,
            '{ use_sgtk != 1 }'
        )
        return sgtk_single_frame

    def _get_template_for_file_path(self, node, file_path):
        is_template = self._work_template.validate(file_path)
        if is_template:
            return self._work_template
        return self._get_template("seq_work_template")

    def _populate_from_fields(self, node, fields):
        super(BaseCacheNodeHandler, self)._populate_from_fields(node, fields)
        sgtk_single_frame = node.parm(self.SGTK_SINGLE_FRAME)
        sgtk_single_frame.set("SEQ" not in fields)
