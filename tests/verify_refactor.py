import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

print("Importing TicketService...")
try:
    from services.ticket_service import TicketService
    print("TicketService imported successfully.")
except Exception as e:
    print(f"FAILED to import TicketService: {e}")
    sys.exit(1)

print("Importing routers.tickets...")
try:
    from routers import tickets
    print("routers.tickets imported successfully.")
except Exception as e:
    print(f"FAILED to import routers.tickets: {e}")
    sys.exit(1)

print("Importing bot.handlers.support_manager...")
try:
    from bot.handlers import support_manager
    print("bot.handlers.support_manager imported successfully.")
except Exception as e:
    print(f"FAILED to import bot.handlers.support_manager: {e}")
    sys.exit(1)

print("Importing bot.handlers.start...")
try:
    from bot.handlers import start
    print("bot.handlers.start imported successfully.")
except Exception as e:
    print(f"FAILED to import bot.handlers.start: {e}")
    sys.exit(1)

print("ALL CHECKS PASSED")
