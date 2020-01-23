def run_after_last_delete(node):
    try:
        import sgtk
    except ImportError:
        pass
    engine = sgtk.platform.current_engine()
    handler = engine.node_handler(node)
    if handler:
        handler.after_last_delete(node=node)


run_after_last_delete(kwargs["node"])
