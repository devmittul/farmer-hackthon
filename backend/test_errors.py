import traceback
import sys

def get_error_message(exc: Exception):
    err_str = str(exc).lower()
    if "429" in err_str or "quota" in err_str or "rate limit" in err_str:
         return "⏳ AI rate limit exceeded or quota exhausted. Please wait a moment."
    elif "401" in err_str or "403" in err_str or "api key" in err_str or "auth" in err_str:
         return "🔑 AI configuration error: Invalid API credentials."
    elif "timeout" in err_str:
         return "⏳ Request timeout: The AI engine took too long to respond."
    elif "connection" in err_str or "network" in err_str:
         return "🌐 Network error: Unable to reach the AI engine."
    elif "satellite" in err_str or "gee" in err_str:
         return "🛰 Satellite service unavailable."
    return "⚠ Internal server error while connecting to the AI engine."

try:
    raise RuntimeError("429 You exceeded your current quota")
except Exception as e:
    print(get_error_message(e))
