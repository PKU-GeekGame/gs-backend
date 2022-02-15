from flask_admin.contrib import sqla, fileadmin # type: ignore
from flask_admin.form import SecureForm # type: ignore
from flask_admin.babel import lazy_gettext # type: ignore
from flask_admin.model.template import macro # type: ignore
from wtforms import validators # type: ignore
from markupsafe import Markup
from flask import current_app, flash
import asyncio
import json
from typing import Any, Optional, Type

from . import fields
from ..logic import glitter
from ..logic.reducer import Reducer
from .. import store

class ViewBase(sqla.ModelView): # type: ignore
    form_base_class = SecureForm
    edit_template = 'edit_ace.html'
    create_template = 'create_ace.html'
    details_modal_template = 'details_break_word.html'

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
    column_default_sort = ('id', True)

    def after_model_touched(self, model: store.AnnouncementStore) -> None:
        self.emit_event(glitter.EventType.UPDATE_ANNOUNCEMENT, model.id)

class ChallengeView(ViewBase):
    can_view_details = True
    details_modal = True

    column_exclude_list = ['desc_template']
    column_default_sort = 'sorting_index'
    column_formatters = {
        'actions': lambda _v, _c, model, _n: '；'.join([f'[{a["type"]}] {a["name"]}' for a in model.actions]),
        'flags': lambda _v, _c, model, _n: '；'.join([f'[{f["type"]} {f["base_score"]}] {f["name"]}' for f in model.flags]),
    }
    form_overrides = {
        'desc_template': fields.MarkdownField,
        'actions': fields.ActionsField,
        'flags': fields.FlagsField,
    }
    form_choices = {
        'category': [(x, x) for x in store.ChallengeStore.CAT_COLORS.keys()],
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
    can_view_details = True

    page_size = 100
    can_set_page_size = True

    column_default_sort = ('id', True)
    column_searchable_list = ['module', 'message']
    column_filters = ['level', 'process', 'module', 'message']

    column_formatters = {
        'timestamp_ms': fields.timestamp_ms_formatter,
        'level': macro('status_label'),
        'message': macro('in_pre'),
    }

class SubmissionView(ViewBase):
    can_create = False
    can_delete = False

    column_display_pk = True
    page_size = 100
    can_set_page_size = True
    column_searchable_list = ['id']
    column_default_sort = ('id', True)

    column_formatters = {
        'timestamp_ms': fields.timestamp_ms_formatter,
    }

    def on_form_prefill(self, *args: Any, **kwargs: Any) -> None:
        flash('WARNING: editing past submissions will reload the scoreboard', 'warning')

    def after_model_touched(self, model: store.ChallengeStore) -> None:
        self.emit_event(glitter.EventType.RELOAD_SUBMISSION)

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

    column_display_pk = True
    page_size = 100
    can_set_page_size = True

    column_searchable_list = ['id']
    column_filters = ['user_id', 'qq_or_null', 'comment_or_null']
    column_default_sort = ('id', True)
    column_formatters = {
        'timestamp_ms': fields.timestamp_ms_formatter,
    }

    def after_model_touched(self, model: store.UserProfileStore) -> None:
        self.emit_event(glitter.EventType.UPDATE_USER, model.user_id)

class UserView(ViewBase):
    can_create = False
    can_delete = False
    can_export = True
    can_view_details = True
    details_modal = True

    column_exclude_list = ['token', 'auth_token', 'login_properties']
    column_display_pk = True
    page_size = 100
    can_set_page_size = True

    column_searchable_list = ['id']
    column_filters = ['group', 'terms_agreed']
    form_choices = {
        'group': list(store.UserStore.GROUPS.items()),
    }
    column_formatters_detail = {
        'login_properties': lambda _v, _c, model, _n: (
            Markup('<samp style="white-space: pre-wrap">%s</samp>') % json.dumps(model.login_properties, indent=4)
        ),
    }
    form_overrides = {
        'login_properties': fields.JsonField,
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

class TemplateView(fileadmin.FileAdmin): # type: ignore
    can_upload = False
    can_mkdir = False
    can_delete = False
    can_delete_dirs = False
    can_rename = False
    editable_extensions = ['md']

    form_base_class = SecureForm
    edit_template = 'edit_ace.html'
    create_template = 'create_ace.html'

    def get_edit_form(self) -> Type[Any]:
        class EditForm(self.form_base_class): # type: ignore
            content = fields.MarkdownField(lazy_gettext('Content'), (validators.InputRequired(),))

        return EditForm

class WriteupView(fileadmin.FileAdmin): # type: ignore
    can_upload = False
    can_mkdir = False
    can_delete = True
    can_delete_dirs = False
    can_rename = False
    can_download = True
    editable_extensions = ['json']

    form_base_class = SecureForm
    edit_template = 'edit_ace.html'
    create_template = 'create_ace.html'

    def get_edit_form(self) -> Type[Any]:
        class EditForm(self.form_base_class): # type: ignore
            content = fields.JsonTextField(lazy_gettext('Content'), (validators.InputRequired(),))

        return EditForm