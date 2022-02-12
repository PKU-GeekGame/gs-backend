from flask_admin.contrib import sqla # type: ignore
from flask_admin.form import SecureForm # type: ignore
from flask import current_app
import asyncio
from typing import Any, Optional

from . import fields
from ..logic import glitter
from ..logic.reducer import Reducer
from .. import store

class ViewBase(sqla.ModelView): # type: ignore
    form_base_class = SecureForm
    edit_template = 'edit_ace.html'
    create_template = 'create_ace.html'

    @staticmethod
    def emit_event(event_type: glitter.EventType, id: Optional[int] = None) -> None:
        loop: asyncio.AbstractEventLoop = current_app.config['reducer_loop']
        reducer: Reducer = current_app.config['reducer_obj']

        async def task() -> None:
            reducer.state_counter += 1
            event = glitter.Event(event_type, reducer.state_counter, id or 0)
            await reducer.emit_event(event)

        asyncio.run_coroutine_threadsafe(task(), loop)

    def after_model_touched(self, model: Any) -> None:
        pass

    def after_model_change(self, form: Any, model: Any, is_created: bool) -> None:
        self.after_model_touched(model)

    def after_model_delete(self, model: Any) -> None:
        self.after_model_touched(model)




class AnnouncementView(ViewBase):
    column_formatters = {
        'timestamp_s': fields.timestamp_s_formatter,
    }
    form_overrides = {
        'timestamp_s': fields.TimestampSField,
        'content_template': fields.MarkdownField,
    }

    def after_model_touched(self, model: store.AnnouncementStore) -> None:
        self.emit_event(glitter.EventType.UPDATE_ANNOUNCEMENT, model.id)

class ChallengeView(ViewBase):
    can_view_details = True
    details_modal = True

    column_exclude_list = ['desc_template']
    form_overrides = {
        'desc_template': fields.MarkdownField,
        'actions': fields.ActionsField,
        'flags': fields.FlagsField,
    }

    def after_model_touched(self, model: store.ChallengeStore) -> None:
        self.emit_event(glitter.EventType.UPDATE_CHALLENGE, model.id)

class GamePolicyView(ViewBase):
    def after_model_touched(self, model: store.GamePolicyStore) -> None:
        self.emit_event(glitter.EventType.RELOAD_GAME_POLICY)

class LogView(ViewBase):
    can_create = False
    can_edit = False
    can_delete = False

    page_size = 100
    can_set_page_size = True

    column_default_sort = ('id', True)
    column_searchable_list = ['module', 'message']
    column_filters = ['level', 'process', 'module', 'message']

    column_formatters = {
        'timestamp_ms': fields.timestamp_ms_formatter,
    }

class SubmissionView(ViewBase):
    can_create = False
    can_edit = False
    can_delete = False

    page_size = 100
    can_set_page_size = True

    column_formatters = {
        'timestamp_ms': fields.timestamp_ms_formatter,
    }

class TriggerView(ViewBase):
    column_formatters = {
        'timestamp_s': fields.timestamp_s_formatter,
    }
    form_overrides = {
        'timestamp_s': fields.TimestampSField,
    }

    def after_model_touched(self, model: store.TriggerStore) -> None:
        self.emit_event(glitter.EventType.RELOAD_TRIGGER)

class UserProfileView(ViewBase):
    can_create = False
    can_delete = False

    page_size = 100
    can_set_page_size = True

    column_searchable_list = ['nickname_or_null', 'qq_or_null']
    column_filters = ['user_id']
    column_formatters = {
        'timestamp_ms': fields.timestamp_ms_formatter,
    }

    def after_model_touched(self, model: store.UserProfileStore) -> None:
        self.emit_event(glitter.EventType.UPDATE_USER, model.user_id)

class UserView(ViewBase):
    can_create = False
    can_delete = False
    can_export = True

    page_size = 100
    can_set_page_size = True

    column_searchable_list = ['id']
    column_filters = ['group', 'terms_agreed']
    form_choices = {
        'group': list(store.UserStore.GROUPS.items()),
    }

    def after_model_touched(self, model: store.UserStore) -> None:
        self.emit_event(glitter.EventType.UPDATE_USER, model.id)

    def on_form_prefill(self, form: Any, id: int) -> None:
        pass

VIEWS = {
    'AnnouncementStore': AnnouncementView,
    'ChallengeStore': ChallengeView,
    'GamePolicyStore': GamePolicyView,
    'LogStore': LogView,
    'SubmissionStore': SubmissionView,
    'TriggerStore': TriggerView,
    'UserStore': UserView,
    'UserProfileStore': UserProfileView,
}