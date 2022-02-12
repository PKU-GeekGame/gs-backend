import wtforms # type: ignore
from markupsafe import Markup
import flask_admin.form # type: ignore
import datetime
from typing import Any, Dict, List

from .. import store
from .. import utils

def timestamp_s_formatter(_view: Any, _context: Any, model: Any, name: str) -> str:
    return utils.format_timestamp(getattr(model, name))

def timestamp_ms_formatter(_view: Any, _context: Any, model: Any, name: str) -> str:
    return utils.format_timestamp(getattr(model, name)/1000)

# noinspection PyAttributeOutsideInit
class TimestampSField(wtforms.fields.IntegerField): # type: ignore
    widget = wtforms.widgets.DateTimeLocalInput()
    def _value(self) -> str:
        if self.data is not None:
            return datetime.datetime.isoformat(datetime.datetime.fromtimestamp(self.data))
        else:
            return ''
    def process_formdata(self, valuelist: List[str]) -> None:
        if valuelist:
            self.data = datetime.datetime.fromisoformat(valuelist[0]).timestamp()
        else:
            self.data = None # type: ignore

# noinspection PyAttributeOutsideInit
class TimestampMsField(wtforms.fields.IntegerField): # type: ignore
    widget = wtforms.widgets.DateTimeLocalInput()
    def _value(self) -> str:
        if self.data is not None:
            return datetime.datetime.isoformat(datetime.datetime.fromtimestamp(self.data/1000))
        else:
            return ''
    def process_formdata(self, valuelist: List[str]) -> None:
        if valuelist:
            self.data = datetime.datetime.fromisoformat(valuelist[0]).timestamp()*1000
        else:
            self.data = None # type: ignore

class AceInput(wtforms.widgets.TextArea): # type: ignore
    def __init__(self) -> None:
        self.unique_id: str = utils.gen_random_str(8)

    def script_body(self) -> str:
        return f'''
            editor.getSession().setValue(textarea.value.trim());
            editor.getSession().on('change', ()=>{'{'}
                textarea.value = editor.getSession().getValue();
            {'}'});
        '''

    def __call__(self, field: wtforms.fields.StringField, **kwargs: Any) -> Markup:
        return Markup(f'''
            <textarea {wtforms.widgets.html_params(name=field.name, id=field.id, **kwargs)} data-ace-id={self.unique_id} readonly>
            {Markup.escape(field._value())}
            </textarea>
            <div class="ace-editor" id="{self.unique_id}"></div>
            
            <script>
                (()=>{'{'}
                    let textarea = document.querySelector('[data-ace-id="{self.unique_id}"]');
                    let editor = ace.edit('{self.unique_id}');
                    window.editor_{self.unique_id} = editor;
                    editor.setTheme("ace/theme/github");
                    editor.session.setUseWrapMode(true);
                    editor.session.setUseSoftTabs(true);
                    {self.script_body()}
                {'}'})();
            </script>
        ''')

class SyntaxHighlightInput(AceInput):
    def __init__(self, lang: str):
        super().__init__()
        self.lang = lang

    def script_body(self) -> str:
        return f'''
            editor.session.setMode("ace/mode/{self.lang}");
            {super().script_body()}
        '''

class JsonListInputWithSnippets(SyntaxHighlightInput):
    def __init__(self, snippets: Dict[str, str]):
        self.snippets = snippets
        super().__init__('javascript')

    def script_body(self) -> str:
        return f'''
            editor.session.setMode("ace/mode/json");
            try {'{'}
                editor.session.setValue(JSON.stringify(JSON.parse(textarea.value||[]), null, "\t"));
            {'}'} catch(e) {'{'}
                editor.session.setValue(textarea.value.trim()||[]);
            {'}'};
            editor.getSession().on('change', ()=>{'{'}
                textarea.value = editor.session.getValue();
            {'}'});
        '''

    def __call__(self, field: wtforms.fields.StringField, **kwargs: Any) -> Markup:
        base_markup = super().__call__(field, **kwargs)

        snippets = [
            f'''
                <button type="button" onclick="append_snippet(editor_{self.unique_id}, '{Markup.escape(v)}');">+{Markup.escape(k)}</button>
            '''
            for k, v in self.snippets.items()
        ]

        return base_markup + Markup(f'''
            <script>
                function append_snippet(editor, s) {'{'}
                    let obj = eval(editor.getValue()); 
                    obj.push(JSON.parse(s));
                    editor.setValue(JSON.stringify(obj, null, "\t"));
                    editor.navigateFileEnd();
                    editor.scrollToLine(Infinity);
                    editor.focus();
                {'}'}
            </script>
            {"".join(snippets)}
        ''')

class MarkdownField(wtforms.fields.TextAreaField): # type: ignore
    widget = SyntaxHighlightInput('markdown')

class FlagsField(flask_admin.form.JSONField): # type: ignore
    widget = JsonListInputWithSnippets(store.ChallengeStore.FLAG_SNIPPETS)

class ActionsField(flask_admin.form.JSONField): # type: ignore
    widget = JsonListInputWithSnippets(store.ChallengeStore.ACTION_SNIPPETS)