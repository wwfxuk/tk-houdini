"""Hook class to handle Houdini Mantra nodes.

Designed to inherit ``base_render_handler`` i.e. define the ``hook`` attribute
in your project configuration settings with the following inheritance:

.. code-block:: yaml
    :caption: env/includes/settings/tk-houdini_node_handlers.yml

    node_handlers.shot_step:
    - node_type: ifd
      node_category: Driver
      hook: "{self}/node_handlers/base_export_handler.py:{self}/node_handlers/base_render_handler.py:{self}/node_handlers/ifd_handler.py"
      work_template: houdini_shot_render
      publish_template: houdini_shot_publish_render
      extra_args:
        aov_work_template: houdini_shot_work_extra_plane
        aov_publish_template: houdini_shot_publish_extra_plane
        dcm_work_template: houdini_shot_work_dcm
        dcm_publish_template: houdini_shot_publish_dcm
        dsm_work_template: houdini_shot_work_dsm
        dsm_publish_template: houdini_shot_publish_dsm
        ifd_work_template: houdini_shot_ifd
        ifd_publish_template: houdini_shot_publish_ifd
        manifest_name_template: houdini_cryptomatte_json_name

"""
import sgtk

import hou

HookBaseClass = sgtk.get_hook_baseclass()


class IfdNodeHandler(HookBaseClass):
    """
    Node handler for mantra renders in Houdini.
    """

    NODE_TYPE = "ifd"
    NODE_CATEGORY = "Driver"

    OUTPUT_PARM = "vm_picture"

    # aovs
    AOV_COUNT = "vm_numaux"
    AOV_NAME_TMPL = "vm_channel_plane{}"
    AOV_FILE_TMPL = "vm_filename_plane{}"
    AOV_USE_FILE_TMPL = "vm_usefile_plane{}"

    # deep output
    VM_DCMFILENAME = "vm_dcmfilename"
    VM_DSMFILENAME = "vm_dsmfilename"

    # cryptomatte
    VM_CRYPTOLAYERS = "vm_cryptolayers"
    VM_CRYPTOLAYERNAME_TMPL = "vm_cryptolayername{}"
    VM_CRYPTOLAYEROUTPUT_TMPL = "vm_cryptolayeroutput{}"
    VM_CRYPTOLAYEROUTPUTENABLE_TMPL = "vm_cryptolayeroutputenable{}"
    VM_CRYPTOLAYERSIDECAR_TMPL = "vm_cryptolayersidecar{}"

    # ifd
    ARCHIVE_ENABLED = "soho_outputmode"
    ARCHIVE_OUTPUT = "soho_diskfile"

    # shotgun
    SGTK_AOV_NAME_TMPL = "sgtk_channel_plane{}"
    SGTK_DEEP_EXT = "sgtk_deep_extension"
    SGTK_CRYPTOLAYERNAME_TMPL = "sgtk_cryptolayername{}"

    # templates
    DCM_WORK_TEMPLATE = "dcm_work_template"
    DCM_PUBLISH_TEMPLATE = "dcm_publish_template"
    DSM_WORK_TEMPLATE = "dsm_work_template"
    DSM_PUBLISH_TEMPLATE = "dsm_publish_template"
    ARCHIVE_WORK_TEMPLATE = "ifd_work_template"
    ARCHIVE_PUBLISH_TEMPLATE = "ifd_publish_template"
    MANIFEST_NAME_TEMPLATE = "manifest_name_template"

    # strings
    AOV_ERROR = "Channel Name not defined"

    def _update_aov_paths(self, node):
        """
        Update all the aov output paths on the node.

        :param node: A :class:`hou.Node` instance.
        """
        super(IfdNodeHandler, self)._update_aov_paths(node)
        vm_cryptolayers = node.parm(self.VM_CRYPTOLAYERS)
        count = vm_cryptolayers.eval() + 1
        for index in range(1, count):
            vm_cryptolayername = node.parm(self.VM_CRYPTOLAYERNAME_TMPL.format(index))
            sgtk_cryptolayername = node.parm(
                self.SGTK_CRYPTOLAYERNAME_TMPL.format(index)
            )
            sgtk_cryptolayername.set(vm_cryptolayername.unexpandedString())
            self._update_crypto_layer_path(node, index)

    def _lock_parms(self, node, lock):
        """
        Lock parms on the node is shotgun is enabled.

        :param node: A :class:`hou.Node` instance.
        :param bool lock: Lock parms if True.
        """
        super(IfdNodeHandler, self)._lock_parms(node, lock)
        parm_names = (self.VM_DCMFILENAME, self.VM_DSMFILENAME)
        for parm_name in parm_names:
            parm = node.parm(parm_name)
            parm.lock(lock)
        self._lock_crypto_parms(node, lock)

    #############################################################################################
    # Overriden methods
    #############################################################################################

    def _customise_parameter_group(self, node, parameter_group, sgtk_folder):
        """
        Here is where you define where the sgtk folder is to be placed, but also
        any other parameters that you wish to add to the node.

        :param node: A :class:`hou.Node` instance.
        :param parameter_group: The node's :class:`ParmGroup`.
        :param sgtk_folder: A :class:`hou.ParmFolderTemplate` containing sgtk
            parameters.
        """
        index = parameter_group.index_of_template("images6")
        parameter_group.insert_template(index, sgtk_folder)

        # Insert sgtk folder before vm_picture
        images_folder = parameter_group.get("images6")

        # aovs
        image_planes_folder = images_folder.get("output6_1")
        vm_numaux = image_planes_folder.get(self.AOV_COUNT)
        vm_numaux_template = vm_numaux.template
        vm_numaux_template.setScriptCallback(
            self.generate_callback_script_str("lock_aov_parms")
        )
        vm_numaux_template.setScriptCallbackLanguage(hou.scriptLanguage.Python)

        index = vm_numaux.index_of_template(self.AOV_NAME_TMPL.format("#"))
        sgtk_aov_name = hou.StringParmTemplate(
            self.SGTK_AOV_NAME_TMPL.format("#"),
            "Channel Name",
            1,
            script_callback=self.generate_callback_script_str("update_aov_path"),
            script_callback_language=hou.scriptLanguage.Python,
        )
        sgtk_aov_name.setConditional(
            hou.parmCondType.DisableWhen,
            '{ vm_disable_plane# == 1 } { vm_variable_plane# == "" }',
        )
        sgtk_aov_name.setConditional(hou.parmCondType.HideWhen, "{ use_sgtk != 1 }")
        vm_numaux.insert_template(index, sgtk_aov_name)

        vm_channel_plane = vm_numaux.get(self.AOV_NAME_TMPL.format("#"))
        vm_channel_plane_template = vm_channel_plane.template
        vm_channel_plane_template.setConditional(
            hou.parmCondType.HideWhen, "{ use_sgtk == 1 }"
        )

        vm_filename_plane = vm_numaux.get(self.AOV_FILE_TMPL.format("#"))
        vm_filename_plane_template = vm_filename_plane.template
        vm_filename_plane_template.setDefaultValue((self.AOV_ERROR,))

        # deep
        deep_folder = images_folder.get("output6_2")
        index = deep_folder.index_of_template(self.VM_DCMFILENAME)
        deep_template_name = self.extra_args.get(self.DCM_WORK_TEMPLATE)
        deep_template = self.parent.get_template_by_name(deep_template_name)
        choices = deep_template.keys["extension"].labelled_choices
        sgtk_deep_ext = hou.MenuParmTemplate(
            self.SGTK_DEEP_EXT,
            "Extension (sgtk only)",
            choices.keys(),
            menu_labels=choices.values(),
            script_callback=self.generate_callback_script_str("update_deep_paths"),
            script_callback_language=hou.scriptLanguage.Python,
        )
        sgtk_deep_ext.setConditional(
            hou.parmCondType.DisableWhen,
            "{ use_sgtk != 1 } { vm_deepresolver == null }",
        )
        deep_folder.insert_template(index, sgtk_deep_ext)

        # cryptomatte
        cryptomatte_folder = images_folder.get("output6_3")
        vm_cryptolayers = cryptomatte_folder.get(self.VM_CRYPTOLAYERS)
        vm_cryptolayers_template = vm_cryptolayers.template
        vm_cryptolayers_template.setScriptCallback(
            self.generate_callback_script_str("lock_crypto_parms")
        )
        vm_cryptolayers_template.setScriptCallbackLanguage(hou.scriptLanguage.Python)

        vm_cryptolayername = vm_cryptolayers.get(
            self.VM_CRYPTOLAYERNAME_TMPL.format("#")
        )
        vm_cryptolayername_template = vm_cryptolayername.template
        vm_cryptolayername_template.setConditional(
            hou.parmCondType.HideWhen, "{ use_sgtk == 1 }"
        )

        vm_cryptolayeroutput = vm_cryptolayers.get(
            self.VM_CRYPTOLAYEROUTPUT_TMPL.format("#")
        )
        vm_cryptolayeroutput_template = vm_cryptolayeroutput.template
        vm_cryptolayeroutput_template.setDefaultValue((self.AOV_ERROR,))

        vm_cryptolayersidecar = vm_cryptolayers.get(
            self.VM_CRYPTOLAYERSIDECAR_TMPL.format("#")
        )
        vm_cryptolayersidecar_template = vm_cryptolayersidecar.template
        vm_cryptolayersidecar_template.setDefaultValue((self.AOV_ERROR,))

        index = vm_cryptolayers.index_of_template(
            self.VM_CRYPTOLAYERNAME_TMPL.format("#")
        )
        sgtk_cryptolayername = hou.StringParmTemplate(
            self.SGTK_CRYPTOLAYERNAME_TMPL.format("#"),
            "Channel Name",
            1,
            default_value=("CryptoMaterial",),
            script_callback=self.generate_callback_script_str(
                "update_crypto_layer_path"
            ),
            script_callback_language=hou.scriptLanguage.Python,
        )
        sgtk_cryptolayername.setConditional(
            hou.parmCondType.HideWhen, "{ use_sgtk != 1 }"
        )
        vm_cryptolayers.insert_template(index, sgtk_cryptolayername)

    def _refresh_file_path(self, node, update_version=True):
        """
        Refresh the file paths generated by the node handler.

        :param node: A :class:`hou.Node` instance.
        :param bool update_version: Update the version drop down accordingly.
        """
        super(IfdNodeHandler, self)._refresh_file_path(
            node, update_version=update_version
        )
        vm_cryptolayers = node.parm(self.VM_CRYPTOLAYERS)
        count = vm_cryptolayers.eval() + 1
        for index in range(1, count):
            self._update_crypto_layer_path(node, index)

        self._update_deep_paths(node)

    #############################################################################################
    # Deep Output
    #############################################################################################

    def _update_deep_paths(self, node):
        """
        Update the output path for deep images.

        :param node: A :class:`hou.Node` instance.
        """
        sgtk_deep_ext = node.parm(self.SGTK_DEEP_EXT)
        extension = sgtk_deep_ext.evalAsString()
        additional_fields = {"extension": extension}
        parm_names = (self.VM_DCMFILENAME, self.VM_DSMFILENAME)
        template_names = (self.DCM_WORK_TEMPLATE, self.DSM_WORK_TEMPLATE)
        for parm_name, template_name in zip(parm_names, template_names):
            self.update_file_path(
                node, parm_name, template_name, additional_fields=additional_fields
            )

    def update_deep_paths(self, kwargs):
        """
        Callback to update the output path for deep images.
        """
        node = kwargs["node"]
        self._update_deep_paths(node)

    #############################################################################################
    # Cryptomatte
    #############################################################################################

    def _update_crypto_layer_path(self, node, index):
        """
        Update cryptomatte later output paths.

        :param node: A :class:`hou.Node` instance.
        :param int index: The index of the aov parm.

        :raises: :class:`FieldInputError` on invalid input.
        """
        parm = node.parm(self.SGTK_CRYPTOLAYERNAME_TMPL.format(index))
        vm_cryptolayername = node.parm(self.VM_CRYPTOLAYERNAME_TMPL.format(index))
        vm_cryptolayeroutput = node.parm(self.VM_CRYPTOLAYEROUTPUT_TMPL.format(index))
        vm_cryptolayersidecar = node.parm(self.VM_CRYPTOLAYERSIDECAR_TMPL.format(index))
        try:
            self._validate_parm(parm)
        except Exception:
            vm_cryptolayername.set("")
            vm_cryptolayeroutput.set(self.AOV_ERROR)
            vm_cryptolayersidecar.set(self.AOV_ERROR)
            raise
        aov = parm.evalAsString()
        vm_cryptolayername.set(parm.unexpandedString())

        channel_path = self.generate_aov_path(node, aov, self.AOV_WORK_TEMPLATE)
        vm_cryptolayeroutput.lock(False)
        vm_cryptolayeroutput.set(channel_path)
        vm_cryptolayeroutput.lock(True)

        sidecar_path = self.generate_aov_path(node, aov, self.MANIFEST_NAME_TEMPLATE)
        vm_cryptolayersidecar.lock(False)
        vm_cryptolayersidecar.set(sidecar_path)
        vm_cryptolayersidecar.lock(True)

    def update_crypto_layer_path(self, kwargs):
        """
        Callback to update cryptomatte later output paths.
        """
        node = kwargs["node"]
        index = kwargs["script_multiparm_index"]
        self._update_crypto_layer_path(node, index)

    def _lock_crypto_parms(self, node, lock):
        """
        Lock the cryptomatte output path parms.

        :param node: A :class:`hou.Node` instance.
        :param bool lock: Lock parms if True.
        """
        vm_cryptolayers = node.parm(self.VM_CRYPTOLAYERS)
        count = vm_cryptolayers.eval() + 1
        for index in range(1, count):
            vm_cryptolayeroutput = node.parm(
                self.VM_CRYPTOLAYEROUTPUT_TMPL.format(index)
            )
            vm_cryptolayeroutput.lock(lock)
            vm_cryptolayersidecar = node.parm(
                self.VM_CRYPTOLAYERSIDECAR_TMPL.format(index)
            )
            vm_cryptolayersidecar.lock(lock)

    def lock_crypto_parms(self, kwargs):
        """
        Callback to lock the cryptomatte output path parms.

        :param node: A :class:`hou.Node` instance.
        :param bool lock: Lock parms if True.
        """
        node = kwargs["node"]
        self._lock_crypto_parms(node, True)

    #############################################################################################
    # Utilities
    #############################################################################################

    def _remove_sgtk_items_from_parm_group(self, parameter_group):
        """
        Remove all sgtk parameters from the node's parameter template group.

        :param ParmGroup parameter_group: The parameter group containing sgtk parameters.
        """
        index = parameter_group.index_of_template(self.SGTK_FOLDER)
        parameter_group.pop_template(index)

        images_folder = parameter_group.get("images6")

        image_planes_folder = images_folder.get("output6_1")
        vm_numaux = image_planes_folder.get(self.AOV_COUNT)
        vm_numaux_template = vm_numaux.template
        vm_numaux_template.setScriptCallback("")

        index = vm_numaux.index_of_template(self.SGTK_AOV_NAME_TMPL.format("#"))
        vm_numaux.pop_template(index)

        vm_filename_plane = vm_numaux.get(self.AOV_FILE_TMPL.format("#"))
        vm_filename_plane_template = vm_filename_plane.template
        vm_filename_plane_template.setDefaultValue(("",))

        deep_folder = images_folder.get("output6_2")
        index = deep_folder.index_of_template(self.SGTK_DEEP_EXT)
        deep_folder.pop_template(index)

        cryptomatte_folder = images_folder.get("output6_3")
        vm_cryptolayers = cryptomatte_folder.get(self.VM_CRYPTOLAYERS)
        vm_cryptolayers_template = vm_cryptolayers.template
        vm_cryptolayers_template.setScriptCallback("")

        index = vm_cryptolayers.index_of_template(
            self.SGTK_CRYPTOLAYERNAME_TMPL.format("#")
        )
        vm_cryptolayers.pop_template(index)

        vm_cryptolayeroutput = vm_cryptolayers.get(
            self.VM_CRYPTOLAYEROUTPUT_TMPL.format("#")
        )
        vm_cryptolayeroutput_template = vm_cryptolayeroutput.template
        vm_cryptolayeroutput_template.setDefaultValue(("$HIP/CryptoMaterial.exr",))

        vm_cryptolayersidecar = vm_cryptolayers.get(
            self.VM_CRYPTOLAYERSIDECAR_TMPL.format("#")
        )
        vm_cryptolayersidecar_template = vm_cryptolayersidecar.template
        vm_cryptolayersidecar_template.setDefaultValue(("CryptoMaterial.json",))

    def _populate_from_fields(self, node, fields):
        """
        Populate the node from template fields.

        :param node: A :class:`hou.Node` instance.
        :param dict fields: The template fields.
        """
        super(IfdNodeHandler, self)._populate_from_fields(node, fields)
        self._populate_aov_names(
            node,
            self.VM_CRYPTOLAYERS,
            self.VM_CRYPTOLAYERNAME_TMPL,
            self.SGTK_CRYPTOLAYERNAME_TMPL,
        )

    def _restore_sgtk_parms(self, node):
        """
        Restore any removed sgtk parameters onto the given node.

        :param node: A :class:`hou.Node` instance containing sgtk parameters.
        """
        vm_dcmfilename = node.parm(self.VM_DCMFILENAME)
        dcm_file_path = vm_dcmfilename.evalAsString()

        super(IfdNodeHandler, self)._restore_sgtk_parms(node)

        dcm_template = self._get_template(self.DCM_WORK_TEMPLATE)

        dcm_fields = dcm_template.validate_and_get_fields(dcm_file_path)
        if dcm_fields:
            sgtk_deep_extension = node.parm(self.SGTK_DEEP_EXT)
            entries = sgtk_deep_extension.menuItems()
            ext = dcm_fields.get("extension", "rat")
            index = entries.index(ext)
            sgtk_deep_extension.set(index)

    def _get_output_paths_and_templates(self, node):
        """
        Go through the node's specified parameters and get the output paths,
        work and publish templates.

        Returns a list of dictionaries, each containing, at least:
        - work template
        - publish template
        - file name

        and optionally:
        - any sequence paths
        - whether the output is a deep image

        :param node: A :class:`hou.Node` instance.

        :rtype: list(dict)
        """
        paths_and_templates = super(
            IfdNodeHandler, self
        )._get_output_paths_and_templates(node)

        # get cryptomatte
        self._get_multi_parm_output_paths_and_templates(
            node,
            self.VM_CRYPTOLAYERS,
            self.VM_CRYPTOLAYEROUTPUTENABLE_TMPL,
            self.VM_CRYPTOLAYEROUTPUT_TMPL,
            self.AOV_WORK_TEMPLATE,
            self.AOV_PUBLISH_TEMPLATE,
            paths_and_templates,
        )

        # get deep outputs
        deep_resolver = node.parm("vm_deepresolver")
        result = deep_resolver.evalAsString()
        if result != "null":
            func_parms = {
                "camera": (
                    node,
                    self.VM_DCMFILENAME,
                    self._get_template(self.DCM_WORK_TEMPLATE),
                    self._get_template(self.DCM_PUBLISH_TEMPLATE),
                    paths_and_templates,
                    True,
                ),
                "shadow": (
                    node,
                    self.VM_DSMFILENAME,
                    self._get_template(self.DSM_WORK_TEMPLATE),
                    self._get_template(self.DSM_PUBLISH_TEMPLATE),
                    paths_and_templates,
                    True,
                ),
            }
            self._get_output_path_and_templates_for_parm(*func_parms[result])

        # get ifd
        if node.parm(self.ARCHIVE_ENABLED).eval():
            self._get_output_path_and_templates_for_parm(
                node,
                self.ARCHIVE_OUTPUT,
                self._get_template(self.ARCHIVE_WORK_TEMPLATE),
                self._get_template(self.ARCHIVE_PUBLISH_TEMPLATE),
                paths_and_templates,
            )

        return paths_and_templates
