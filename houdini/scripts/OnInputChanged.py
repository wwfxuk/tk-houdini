def run_on_input_changed(node):
    try:
        import sgtk
    except ImportError:
        pass
    engine = sgtk.platform.current_engine()
    handler = engine.node_handler(node)
    if handler:
        handler.on_input_changed(node=node)


run_on_input_changed(kwargs["node"])
