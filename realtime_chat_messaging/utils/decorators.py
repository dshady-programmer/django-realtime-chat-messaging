from functools import wraps

def event_handler(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        
        except Exception as e:
            self = args[0]
            await self.send(text_data=json.dumps({"error": str(e)}))
            print(f"Error in {func.__name__}: {e}")
    return wrapper
