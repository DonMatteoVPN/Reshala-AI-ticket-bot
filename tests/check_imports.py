
import sys
import os

# Add backend to path
sys.path.append(os.path.abspath("backend"))

try:
    print("Checking imports...")
    from bot.handlers import support
    print("Direct import 'bot.handlers.support' OK")
    
    from bot.handlers.support_client import handle_client_message
    print("Import 'support_client' OK")
    
    from bot.handlers.support_manager import handle_support_group_message
    print("Import 'support_manager' OK")
    
    from bot.main import main
    print("Import 'bot.main' OK")
    
    print("ALL IMPORTS OK")
except Exception as e:
    print(f"IMPORT ERROR: {e}")
    import traceback
    traceback.print_exc()
