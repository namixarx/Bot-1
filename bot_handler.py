"""
Telegram Bot Handler
Handles polling and message processing for all active bots
"""
import threading
import time
from telegram.ext import Application, MessageHandler, filters, CallbackQueryHandler
from models import db, Bot as BotModel, Message, Button
from config import Config
from flask import Flask

# Global dictionary to store bot applications
bot_applications = {}
bot_threads = {}


def get_bot_response(app, bot_id, user_message):
    """
    Get the appropriate response for a message based on bot configuration
    Priority: Buttons first, then auto-reply messages
    """
    try:
        with app.app_context():
            # Check buttons first (case-insensitive)
            buttons = Button.query.filter_by(bot_id=bot_id).all()
            print(f"DEBUG: Checking {len(buttons)} buttons for bot {bot_id}")
            for button in buttons:
                if button.button_text.lower() in user_message.lower():
                    print(f"DEBUG: Matched button '{button.button_text}' for bot {bot_id}")
                    return button.response_text
            
            # Then check auto-reply messages (case-insensitive)
            messages = Message.query.filter_by(bot_id=bot_id).all()
            print(f"DEBUG: Checking {len(messages)} messages for bot {bot_id}")
            for message in messages:
                if message.trigger_text.lower() in user_message.lower():
                    print(f"DEBUG: Matched trigger '{message.trigger_text}' for bot {bot_id}")
                    return message.response_text
            
            print(f"DEBUG: No match found for bot {bot_id}")
            return None
    except Exception as e:
        print(f"ERROR in get_bot_response: {e}")
        import traceback
        traceback.print_exc()
        return None


async def handle_message(update, context):
    """Handle incoming messages"""
    try:
        bot_id = context.bot_data.get('bot_id')
        app = context.bot_data.get('app')
        if not bot_id or not app:
            print(f"ERROR: Missing bot_id or app in context. bot_id={bot_id}, app={app}")
            return
        
        if not update.message or not update.message.text:
            return
        
        user_message = update.message.text
        print(f"DEBUG: Received message for bot {bot_id}: '{user_message}'")
        
        response = get_bot_response(app, bot_id, user_message)
        if response:
            print(f"DEBUG: Sending response for bot {bot_id}: '{response[:50]}...'")
            await update.message.reply_text(response)
        else:
            print(f"DEBUG: No matching trigger found for bot {bot_id}, message: '{user_message}'")
    except Exception as e:
        print(f"ERROR in handle_message: {e}")
        import traceback
        traceback.print_exc()


async def handle_button_click(update, context):
    """Handle button/callback query clicks"""
    try:
        bot_id = context.bot_data.get('bot_id')
        app = context.bot_data.get('app')
        if not bot_id or not app:
            print(f"ERROR: Missing bot_id or app in button handler. bot_id={bot_id}, app={app}")
            return
        
        query = update.callback_query
        if not query:
            return
            
        button_text = query.data
        print(f"DEBUG: Received button click for bot {bot_id}: '{button_text}'")
        
        # Find button by text
        with app.app_context():
            button = Button.query.filter_by(bot_id=bot_id, button_text=button_text).first()
            if button:
                print(f"DEBUG: Matched button '{button.button_text}' for bot {bot_id}")
                await query.answer()
                await query.edit_message_text(text=button.response_text)
            else:
                print(f"DEBUG: No button found matching '{button_text}' for bot {bot_id}")
    except Exception as e:
        print(f"ERROR in handle_button_click: {e}")
        import traceback
        traceback.print_exc()


def create_bot_application(bot_model, app):
    """Create a Telegram bot application for a bot model"""
    try:
        print(f"DEBUG: Creating application for bot {bot_model.name} (ID: {bot_model.id})")
        application = Application.builder().token(bot_model.token).build()
        
        # Store bot_id and app in bot_data for handlers
        application.bot_data['bot_id'] = bot_model.id
        application.bot_data['app'] = app
        
        # Add handlers - make sure they're added before starting
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.add_handler(CallbackQueryHandler(handle_button_click))
        
        print(f"DEBUG: Application created successfully for bot {bot_model.name}")
        print(f"DEBUG: Handlers added - MessageHandler and CallbackQueryHandler")
        return application
    except Exception as e:
        print(f"ERROR: Error creating bot application for {bot_model.name}: {e}")
        print(f"  Token: {bot_model.token[:10]}... (truncated for security)")
        import traceback
        traceback.print_exc()
        return None


def run_bot_polling(bot_id, application):
    """Run polling for a bot in a separate thread"""
    import asyncio
    try:
        print(f"DEBUG: Starting polling for bot {bot_id}")
        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Use run_polling which handles initialization automatically for v20.x
        application.run_polling(
            allowed_updates=["message", "callback_query"],
            drop_pending_updates=True,
            stop_signals=None  # Don't handle signals in thread
        )
        print(f"DEBUG: Polling started successfully for bot {bot_id}")
    except Exception as e:
        print(f"ERROR: Error in polling for bot {bot_id}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            loop.close()
        except:
            pass


def start_bot(bot_model, app):
    """Start a bot's polling"""
    if bot_model.id in bot_applications:
        # Bot already running
        print(f"Bot {bot_model.name} (ID: {bot_model.id}) is already running")
        return
    
    if not bot_model.is_active:
        print(f"Bot {bot_model.name} (ID: {bot_model.id}) is not active, skipping start")
        return
    
    print(f"Attempting to start bot: {bot_model.name} (ID: {bot_model.id})")
    print(f"  Token: {bot_model.token[:15]}... (truncated)")
    print(f"  Active: {bot_model.is_active}")
    
    application = create_bot_application(bot_model, app)
    if not application:
        print(f"ERROR: Failed to create bot application for {bot_model.name}")
        return
    
    bot_applications[bot_model.id] = application
    
    # Start polling in a separate thread
    thread = threading.Thread(
        target=run_bot_polling,
        args=(bot_model.id, application),
        daemon=True,
        name=f"BotPolling-{bot_model.id}"
    )
    thread.start()
    bot_threads[bot_model.id] = thread
    
    # Give the thread a moment to start
    import time
    time.sleep(1)  # Increased wait time
    
    if thread.is_alive():
        print(f"SUCCESS: Started bot: {bot_model.name} (ID: {bot_model.id}) - Polling active")
        print(f"  Thread ID: {thread.ident}")
        print(f"  Thread name: {thread.name}")
        print(f"  Thread alive: {thread.is_alive()}")
    else:
        print(f"WARNING: Thread for bot {bot_model.name} (ID: {bot_model.id}) may have failed to start")


def stop_bot(bot_id):
    """Stop a bot's polling"""
    if bot_id in bot_applications:
        try:
            print(f"Stopping bot ID: {bot_id}")
            application = bot_applications[bot_id]
            
            # Stop the updater if it's running
            if hasattr(application, 'updater') and hasattr(application.updater, 'running') and application.updater.running:
                application.updater.stop()
                print(f"  Stopped updater for bot {bot_id}")
            
            # Stop and shutdown the application
            application.stop()
            application.shutdown()
            
            del bot_applications[bot_id]
            if bot_id in bot_threads:
                del bot_threads[bot_id]
            print(f"SUCCESS: Stopped bot ID: {bot_id}")
        except Exception as e:
            print(f"ERROR: Error stopping bot {bot_id}: {e}")
            import traceback
            traceback.print_exc()


def update_bot_statuses(app):
    """Update bot statuses - start active bots, stop inactive ones"""
    with app.app_context():
        # Get all bots
        all_bots = BotModel.query.all()
        
        # Start active bots that aren't running
        for bot in all_bots:
            if bot.is_active and bot.id not in bot_applications:
                start_bot(bot, app)
            elif not bot.is_active and bot.id in bot_applications:
                stop_bot(bot.id)


def initialize_bots(app):
    """Initialize all active bots on startup"""
    with app.app_context():
        active_bots = BotModel.query.filter_by(is_active=True).all()
        for bot in active_bots:
            start_bot(bot, app)
        print(f"Initialized {len(active_bots)} active bot(s)")


def monitor_bots(app):
    """Monitor bot statuses periodically"""
    while True:
        try:
            time.sleep(10)  # Check every 10 seconds
            update_bot_statuses(app)
        except Exception as e:
            print(f"Error in bot monitor: {e}")
            time.sleep(30)  # Wait longer on error

