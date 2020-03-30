def run_on_loaded(node):
    try:
        import sgtk
    except ImportError:
        return
    engine = sgtk.platform.current_engine()
    if engine:
        handler = engine.node_handler(node)
        if handler:
            handler.on_loaded(node=node)


run_on_loaded(kwargs["node"])
