from flask_admin.contrib import sqla, fileadmin
from flask_admin.form import SecureForm
from flask_admin.babel import lazy_gettext
from flask_admin.model.template import macro
from flask_admin import AdminIndexView, expose
from wtforms import validators
from markupsafe import Markup
from flask import current_app, flash, redirect, url_for
import asyncio
import json
import time
import psutil
from flask.typing import ResponseReturnValue
from typing import Any, Optional, Type, Dict

from ..state import Trigger
from . import fields
from ..logic import glitter
from ..logic.reducer import Reducer
from .. import store

class StatusView(AdminIndexView):  # type: ignore
    @expose('/')
    def index(self) -> ResponseReturnValue:
        reducer: Reducer = current_app.config['reducer_obj']
        reducer.received_telemetries['Reducer'] = (time.time(), reducer.collect_telemetry())

        USER_STATUS = {
            'disabled': '已禁用',
            'pending_terms': '未同意条款',
            'pending_profile': '未完善信息',
            'no_score': '无成绩',
            'have_score': '有成绩',
        }

        TELEMETRY_FIELDS = {
            'last_update': '更新时间',
            'ws_online_clients': '在线连接',
            'ws_online_uids': '在线用户',
            'state_counter': '状态编号',
            'game_available': '比赛可用',
            'cur_tick': 'Tick',
            'n_users': '用户数',
            'n_submissions': '提交数',
        }

        vmem = psutil.virtual_memory()
        smem = psutil.swap_memory()
        disk = psutil.disk_usage('/')
        G = 1024**3
        sys_status = {
            'process': f'{len(psutil.pids())}',
            'load': ' '.join(str(l) for l in psutil.getloadavg()),
            'ram': f'total={vmem.total/G:.2f}G, used={vmem.used/G:.2f}G, available={vmem.available/G:.2f}G',
            'swap': f'total={smem.total/G:.2f}G, used={smem.used/G:.2f}G, free={smem.free/G:.2f}G',
            'disk': f'total={disk.total/G:.2f}G, used={disk.used/G:.2f}G, free={disk.free/G:.2f}G',
        }

        users_cnt_by_group: Dict[str, Dict[str, int]] = {}

        for u in reducer._game.users.list:
            u_group = u._store.group

            if not u._store.enabled:
                u_status = 'disabled'
            elif not u._store.terms_agreed:
                u_status = 'pending_terms'
            elif u._store.profile.check_profile(u._store.group) is not None:
                u_status = 'pending_profile'
            elif u.tot_score==0:
                u_status = 'no_score'
            else:
                u_status = 'have_score'

            users_cnt_by_group.setdefault(u_group, {}).setdefault(u_status, 0)
            users_cnt_by_group[u_group][u_status] += 1

        return self.render(
            'status.html',

            sys_status=sys_status,

            user_fields=USER_STATUS,
            user_data=users_cnt_by_group,

            tel_fields=TELEMETRY_FIELDS,
            tel_data={
                worker_name: {
                    'last_update': f'{int(time.time()-last_update):d}s',
                    **tel_dict,
                } for worker_name, (last_update, tel_dict) in reducer.received_telemetries.items()
            },
        )

    @expose('/clear_telemetry')
    def clear_telemetry(self) -> ResponseReturnValue:
        reducer: Reducer = current_app.config['reducer_obj']
        reducer.received_telemetries.clear()
        return redirect(url_for('.index'))

    @expose('/test_push')
    def test_push(self) -> ResponseReturnValue:
        loop: asyncio.AbstractEventLoop = current_app.config['reducer_loop']
        reducer: Reducer = current_app.config['reducer_obj']

        async def run_push() -> None:
            reducer.log('error', 'admin.test_push', 'test push message')

        asyncio.run_coroutine_threadsafe(run_push(), loop)
        return redirect(url_for('.index'))

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
    column_descriptions = {
        'content_template': '支持 Markdown 和 Jinja2 模板（group: Optional[str]、tick: int）',
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
    column_descriptions = {
        'effective_after': '题目从该 Tick 编号后对选手可见',
        'key': '题目唯一 ID，将会显示在 URL 中，比赛中不要随意修改，否则会导致已有提交失效',
        'sorting_index': '越小越靠前',
        'desc_template': '支持 Markdown 和 Jinja2 模板（group: Optional[str]、tick: int）',
        'actions': '题面底部展示的动作列表',
    }
    form_overrides = {
        'desc_template': fields.MarkdownField,
        'actions': fields.ActionsField,
        'flags': fields.FlagsField,
    }
    form_choices = {
        'category': [(x, x) for x in store.ChallengeStore.CAT_COLORS.keys()],
    }

    def on_form_prefill(self, *args: Any, **kwargs: Any) -> None:
        flash('警告：增删题目或者修改 flags 字段会重算排行榜', 'warning')

    def after_model_touched(self, model: store.ChallengeStore) -> None:
        self.emit_event(glitter.EventType.UPDATE_CHALLENGE, model.id)

class GamePolicyView(ViewBase):
    column_descriptions = {
        'effective_after': '策略从该 Tick 编号后生效',
    }

    def on_form_prefill(self, *args: Any, **kwargs: Any) -> None:
        flash('警告：修改赛程配置会重算排行榜', 'warning')

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

def _flag_match_formatter(_view: Any, _context: Any, model: store.SubmissionStore, _name: str) -> str:
    reducer: Reducer = current_app.config['reducer_obj']
    sub = reducer._game.submissions.get(model.id, None)

    if sub is None:
        return '???'

    if sub.matched_flag:
        return f'{sub.matched_flag.name or "FLAG"} (+{sub.gained_score()})'
    elif sub.duplicate_submission:
        return '(duplicate)'
    else:
        return ''

def _flag_override_formatter(_view: Any, _context: Any, model: store.SubmissionStore, _name: str) -> str:
    ret = []
    if model.score_override_or_null is not None:
        ret.append(f'[={model.score_override_or_null}]')
    if model.precentage_override_or_null is not None:
        ret.append(f'[*{model.precentage_override_or_null}%]')

    return ' '.join(ret)

class SubmissionView(ViewBase):
    can_create = False
    can_delete = False

    column_list = ['id', 'timestamp_ms', 'user_.profile.nickname_or_null', 'user_.group', 'challenge_key', 'flag', 'matched_flag', 'override']

    column_display_pk = True
    page_size = 100
    can_set_page_size = True
    column_searchable_list = ['id']
    column_default_sort = ('id', True)

    column_labels = {
        'user_.profile.nickname_or_null': 'User Nickname',
        'user_.group': 'User Group',
    }
    column_descriptions = {
        'score_override_or_null': '将选手分数覆盖为此值',
        'precentage_override_or_null': '将选手分数乘以此百分比，当 score_override_or_null 存在时此设置不生效',
    }
    column_formatters = {
        'timestamp_ms': fields.timestamp_ms_formatter,
        'matched_flag': _flag_match_formatter,
        'override': _flag_override_formatter,
    }

    def on_form_prefill(self, *args: Any, **kwargs: Any) -> None:
        flash('警告：修改历史提交会重算排行榜', 'warning')

    def after_model_touched(self, model: store.ChallengeStore) -> None:
        self.emit_event(glitter.EventType.RELOAD_SUBMISSION)

class TriggerView(ViewBase):
    column_descriptions = {
        'tick': f'Tick 编号，应为自然数且随时间递增，排行榜横轴范围是 Tick {Trigger.TRIGGER_BOARD_BEGIN} ~ {Trigger.TRIGGER_BOARD_END}',
        'name': '将在前端展示，半角分号表示换行',
    }
    column_formatters = {
        'timestamp_s': fields.timestamp_s_formatter,
    }
    form_overrides = {
        'timestamp_s': fields.TimestampSField,
    }

    def on_form_prefill(self, *args: Any, **kwargs: Any) -> None:
        flash('警告：修改赛程配置会重算排行榜', 'warning')

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

    column_descriptions = {
        'timestamp_ms': '用户保存此信息的时间',
    }
    column_formatters = {
        'timestamp_ms': fields.timestamp_ms_formatter,
    }

    def after_model_touched(self, model: store.UserProfileStore) -> None:
        self.emit_event(glitter.EventType.UPDATE_USER, model.user_id)

def _user_oauth_info_formatter(_view: Any, _context: Any, model: store.UserStore, _name: str) -> str:
    props = model.login_properties
    if props['type']=='iaaa':
        return f'[IAAA] {props["info"]["name"]}（{props["info"]["dept"]} {props["info"]["detailType"]} {props["info"]["identityStatus"]}）'
    elif props['type']=='microsoft':
        return f'[MS] {props["info"]["displayName"]}（{props["info"]["userPrincipalName"]}）'
    elif props['type']=='github':
        return f'[GitHub] {props["info"]["login"]}（{props["info"]["name"]}）'
    else:
        return f'[{props["type"]}]'

def _user_game_status_formatter(_view: Any, _context: Any, model: store.UserStore, _name: str) -> str:
    reducer: Reducer = current_app.config['reducer_obj']
    user = reducer._game.users.user_by_id.get(model.id, None)

    if user is None:
        return '???'

    res = user.check_play_game()
    if res is None:
        return 'OK'
    else:
        return res[1]

class UserView(ViewBase):
    can_create = False
    can_delete = False
    can_export = True
    can_view_details = True
    details_modal = True

    column_list = ['id', 'profile.nickname_or_null', 'group', 'profile.qq_or_null', 'oauth_info', 'game_status', 'timestamp_ms']
    column_exclude_list = ['token', 'auth_token', 'login_properties']
    column_display_pk = True
    page_size = 100
    can_set_page_size = True

    column_searchable_list = ['id']
    column_filters = ['group', 'terms_agreed']
    column_labels = {
        'profile.nickname_or_null': 'Nickname',
        'profile.qq_or_null': 'QQ',
    }
    form_choices = {
        'group': list(store.UserStore.GROUPS.items()),
    }

    column_descriptions = {
        'login_key': 'OAuth Provider 提供的唯一 ID，用于判断用户是注册还是登录',
        'login_properties': 'OAuth Provider 提供的用户信息',
        'timestamp_ms': '注册时间',
        'enabled': '是否允许登录',
        'token': '在前端展示，平台本身不使用',
        'auth_token': '登录凭据，登录后会存在 Cookie 里',
    }
    column_formatters = {
        'timestamp_ms': fields.timestamp_ms_formatter,
        'oauth_info': _user_oauth_info_formatter,
        'game_status': _user_game_status_formatter,
    }
    column_formatters_detail = {
        'login_properties': lambda _v, _c, model, _n: (
            Markup('<samp style="white-space: pre-wrap">%s</samp>') % json.dumps(model.login_properties, indent=4, ensure_ascii=False)
        ),
    }
    form_overrides = {
        'login_properties': fields.JsonField,
    }

    def on_form_prefill(self, *args: Any, **kwargs: Any) -> None:
        flash('警告：删除用户或者修改 group 字段会重算排行榜', 'warning')

    def after_model_touched(self, model: store.UserStore) -> None:
        self.emit_event(glitter.EventType.UPDATE_USER, model.id)

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

# fix crlf and encoding on windows
class FileAdmin(fileadmin.BaseFileAdmin):  # type: ignore
    class FixingCrlfFileStorage(fileadmin.LocalFileStorage):  # type: ignore
        def write_file(self, path: str, content: str) -> int:
            with open(path, 'w', encoding='utf-8') as f:
                return f.write(content.replace('\r\n', '\n'))

    def __init__(self, base_path: str, *args: Any, **kwargs: Any) -> None:
        storage = self.FixingCrlfFileStorage(base_path)
        super().__init__(*args, storage=storage, **kwargs)

class TemplateView(FileAdmin):
    can_upload = True
    can_mkdir = False
    can_delete = False
    can_delete_dirs = False
    can_rename = False
    editable_extensions = ['md']

    form_base_class = SecureForm
    edit_template = 'edit_ace.html'

    def get_edit_form(self) -> Type[Any]:
        class EditForm(self.form_base_class): # type: ignore
            content = fields.MarkdownField(lazy_gettext('Content'), (validators.InputRequired(),))

        return EditForm

class WriteupView(FileAdmin):
    can_upload = False
    can_mkdir = False
    can_delete = False
    can_delete_dirs = False
    can_rename = False
    can_download = True
    editable_extensions = ['json']

    form_base_class = SecureForm
    edit_template = 'edit_ace.html'

    def get_edit_form(self) -> Type[Any]:
        class EditForm(self.form_base_class): # type: ignore
            content = fields.JsonTextField(lazy_gettext('Content'), (validators.InputRequired(),))

        return EditForm

class FilesView(FileAdmin):
    can_upload = True
    can_mkdir = True
    can_delete = True
    can_delete_dirs = True
    can_rename = True
    can_download = True
    editable_extensions = ['py']

    form_base_class = SecureForm
    edit_template = 'edit_ace.html'

    def get_edit_form(self) -> Type[Any]:
        class EditForm(self.form_base_class): # type: ignore
            content = fields.PythonField(lazy_gettext('Content'), (validators.InputRequired(),))

        return EditForm