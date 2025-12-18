from functools import wraps
import json

def event_handler(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        
        except Exception as e:
            self = args[0]
            await self.send(text_data=json.dumps({"error": str(e)}))
            # import traceback
            # traceback.print_exc()
            print(f"Error in {func.__name__}: {e}")
    return wrapper
