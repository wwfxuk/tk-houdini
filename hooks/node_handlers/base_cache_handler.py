"""Base Hook for other Houdini cache output node handlers.

These include:

- ``alembic_handler``
- ``geometry_handler``

This hook is designed to inherit from ``base_export_handler`` hook.
"""
import sgtk

import hou


HookBaseClass = sgtk.get_hook_baseclass()


class BaseCacheNodeHandler(HookBaseClass):
    """
    Base class for any cache export nodes.
    """

    SGTK_SINGLE_FRAME = "sgtk_single_frame"

    def _is_single_frame(self, node):
        """
        Check if the output is a single file or a sequence.

        :param node: A :class:`hou.Node` instance.

        :rtype: bool
        """
        sgtk_single_frame = node.parm(self.SGTK_SINGLE_FRAME)
        if sgtk_single_frame:
            return bool(sgtk_single_frame.eval())
        return True

    def get_work_template(self, node):
        """
        Get the shotgun work template for this node handler.
        Sequence paths require a different template.

        :param node: A :class:`hou.Node` instance.

        :rtype: An :class:`sgtk.Template` instance.
        """
        if self._is_single_frame(node):
            return self._work_template
        return self._get_template("seq_work_template")

    def get_publish_template(self, node):
        """
        Get the shotgun publish template for this node handler.
        Sequence paths require a different template.

        :param node: A :class:`hou.Node` instance.

        :rtype: An :class:`sgtk.Template` instance.
        """
        if self._is_single_frame(node):
            return self._publish_template
        return self._get_template("seq_publish_template")

    def _build_single_file_parm(self, default):
        """
        Build a template for the single file parm.

        :param bool default: The default check state of the parm.

        :returns: A :class:`hou.ToggleParmTemplate` instance.
        """
        sgtk_single_frame = hou.ToggleParmTemplate(
            self.SGTK_SINGLE_FRAME,
            "Single File",
            default_value=default,
            script_callback=self.generate_callback_script_str("refresh_file_path"),
            script_callback_language=hou.scriptLanguage.Python,
        )
        sgtk_single_frame.setConditional(
            hou.parmCondType.DisableWhen, "{ use_sgtk != 1 }"
        )
        return sgtk_single_frame

    def _get_template_for_file_path(self, node, file_path):
        """
        Get the template for the given file path.
        For the most part, this will liekly be the work_template.

        :param node: A :class:`hou.Node` instance.
        :param str file_path: The file path the check against.

        :rtype: :class:`sgtk.Template`
        """
        if self._work_template.validate(file_path):
            return self._work_template
        return self._get_template("seq_work_template")

    def _populate_from_fields(self, node, fields):
        """
        Populate the node from template fields.

        :param node: A :class:`hou.Node` instance.
        :param dict fields: The template fields.
        """
        super(BaseCacheNodeHandler, self)._populate_from_fields(node, fields)
        sgtk_single_frame = node.parm(self.SGTK_SINGLE_FRAME)
        sgtk_single_frame.set("SEQ" not in fields)
