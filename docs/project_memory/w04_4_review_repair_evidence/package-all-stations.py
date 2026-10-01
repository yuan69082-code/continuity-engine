"""One package run; observe every original C1 prepare because first run stopped earlier."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
source=(ROOT/'docs/project_memory/w04_4_evidence/full-errors-stations-01.py').read_text(encoding='utf8')
source=source.replace("    if kwargs.get('entry') != 'entry:B' or not kwargs.get('reply_to'):\n        return original_submit(self, text, **kwargs)\n",'')
source=source.replace("            (self.entries,'origins','entry.origins'),", """            (self.entries,'origins','entry.origins'),
            (self.entries,'scoped_state','entry.scoped-state'),
            (self.entries,'_state_lineage','entry.lineage'),
            (self.entries,'_fragment_origins','entry.fragment'),
            (self.entries.native_thinking._repository,'_load_projection','thinking.projection'),""")
source=source.replace(" 'test_w04_4_continuity.CrossEntryTests.test_simulated_ui_question_followup_reply_same_engine_and_matter',\n",'')
exec(compile(source,str(Path(__file__).resolve()),'exec'))
