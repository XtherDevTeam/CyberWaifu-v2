import time

def TimeProvider() -> str:
    return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())


def DateProvider() -> str:
    return time.strftime('%Y-%m-%d', time.localtime())


def retryWrapper(func, max_retries=3, retry_interval=1):
    for i in range(max_retries):
        try:
            return func()
        except Exception as e:
            print(f"Error: {e}, retrying in {retry_interval} seconds...")
            time.sleep(retry_interval)
    return func()