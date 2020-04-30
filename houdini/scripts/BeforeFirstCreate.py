def run_before_first_create(node):
    try:
        import sgtk
    except ImportError:
        return
    engine = sgtk.platform.current_engine()
    if engine:
        handler = engine.node_handler(node)
        if handler:
            handler.before_first_create(node=node)


run_before_first_create(kwargs["node"])
