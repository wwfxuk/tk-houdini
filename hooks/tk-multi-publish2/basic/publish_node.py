import sgtk
import os

HookBaseClass = sgtk.get_hook_baseclass()


class HoudiniNodePublishPlugin(HookBaseClass):
    """
    This hook handles whether to accept, and the validation and publishes
    for the Render node item.  This doesn't actually publish anything
    but acts as a parent to ``render output items`` and the render session.
    """

    @property
    def icon(self):
        """
        The path to an icon on disk that is representative of this plugin
        (:class:`str`).
        """
        return os.path.join(self.disk_location, "icons", "houdini.png")

    @property
    def description(self):
        """
        Verbose, multi-line description of what the plugin does. This can
        contain simple html for formatting (:class:`str`)
        """
        return "Publishes all the outputs associated with this node."

    @property
    def settings(self):
        """
        Dictionary defining the settings that this plugin expects to recieve
        through the settings parameter in the accept, validate, publish and
        finalize methods.
        A dictionary on the following form::
            {
                "Settings Name": {
                    "type": "settings_type",
                    "default": "default_value",
                    "description": "One line description of the setting"
            }
        The type string should be one of the data types that toolkit accepts
        as part of its environment configuration.

        There are no settings for this item.

        :returns: A dictionary of settings.
        """
        # inherit the settings from the base publish plugin
        return {}

    @property
    def item_filters(self):
        """
        List of item types that this plugin is interested in.
        Only items matching entries in this list will be presented to the
        accept() method. Strings can contain glob patters such as *, for example
        ["katana.*", "katana.session"]
        """
        return ["houdini.node.*"]

    def accept(self, settings, item):
        """
        Method called by the publisher to determine if an item is of any
        interest to this plugin. Only items matching the filters defined via the
        item_filters property will be presented to this method.
        A publish task will be generated for each item accepted here. Returns a
        dictionary with the following booleans:

        - accepted: Indicates if the plugin is interested in this value at
          all. Required.
        - enabled: If True, the plugin will be enabled in the UI, otherwise
          it will be disabled. Optional, True by default.
        - visible: If True, the plugin will be visible in the UI, otherwise
          it will be hidden. Optional, True by default.
        - checked: If True, the plugin will be checked in the UI, otherwise
          it will be unchecked. Optional, True by default.

        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process.

        :returns: dictionary with boolean keys accepted, visible, required and enabled.
        """
        # Naively accept all renders which have valid outputs
        item.expanded = False
        if not item._children:
            return {"accepted": False}
        return {"accepted": True, "checked": False}

    def validate(self, settings, item):
        """
        Validates the given item to check that it is ok to publish.

        Returns a boolean to indicate validity.

        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process

        :returns: True if item is valid, False otherwise.
        """
        return True

    def publish(self, settings, item):
        """
        Inherits the publish data from the parent item to pass to the child
        ``render output items``.

        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process.
        """
        scene_publish_data = item.parent.properties.get("sg_publish_data")
        if scene_publish_data:
            self.logger.debug("Getting sg_publish_data '{}' from parent".format(scene_publish_data))
            item.properties["sg_publish_data"] = scene_publish_data

    def finalize(self, settings, item):
        """
        Does nothing.

        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process
        """
        return
