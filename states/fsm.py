"""All FSM state groups for the bot."""
from aiogram.fsm.state import State, StatesGroup


class OrderFlow(StatesGroup):
    # Step 1 – collect the channel URL (if not entered directly)
    entering_channel = State()
    # Step 2 – pick what to order
    choosing_mode = State()
    # Step 3a – subscribers
    subs_service_id = State()
    subs_quantity = State()
    # Step 3b – views
    views_service_id = State()
    views_quantity = State()
    # Step 3c – reactions
    reactions_service_id = State()
    reactions_quantity = State()
    # Step 4 – preset selection (alternative path)
    choosing_preset = State()
    # Step 5 – final confirmation
    confirming = State()


class PresetFlow(StatesGroup):
    entering_name = State()
    # Subscribers section
    subs_enabled = State()
    subs_service_id = State()
    subs_quantity = State()
    # Views section
    views_enabled = State()
    views_service_id = State()
    views_quantity = State()
    # Reactions section
    reactions_enabled = State()
    reactions_service_id = State()
    reactions_quantity = State()
    # Post count
    post_count = State()
    # Confirmation
    confirming = State()


class DeletePresetFlow(StatesGroup):
    choosing_preset = State()
    confirming = State()


class TelethonAuth(StatesGroup):
    waiting_for_code = State()
    waiting_for_password = State()
