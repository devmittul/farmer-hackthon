import traceback
try:
    1 / 0
except Exception as e:
    exc_type = type(e).__name__
    try:
        tb_str = "".join(traceback.format_exception(exc_type, e, e.__traceback__))
        print(tb_str)
    except Exception as e2:
        print("Failed string:", e2)
    try:
        tb_str = "".join(traceback.format_exception(type(e), e, e.__traceback__))
        print(tb_str)
    except Exception as e2:
        print("Failed type:", e2)
