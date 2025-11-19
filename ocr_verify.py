import io
import sys
from pathlib import Path
from backend.services.resume_parser import parse_uploaded_files_to_df
from backend.services.ai_matcher import ai_match_resumes_df

pdf_path = Path(r'c:/RecruitFlow_Pro_MVP/【数学竞赛教练_北京】路老师 7�?pdf')

class UploadedFile:
    def __init__(self, path: Path):
        self.name = path.name
        self._bytes = path.read_bytes()
    def getbuffer(self, *args, **kwargs):
        return io.BytesIO(self._bytes).getbuffer()

print('>>> 开�?OCR 解析...')
files = [UploadedFile(pdf_path)]
df = parse_uploaded_files_to_df(files, max_chars=200000)
if df.empty:
    print('解析结果为空，无法继续�?)
    sys.exit(1)
row = df.iloc[0]
resume_text = row['resume_text']
text_len = len(resume_text)
print('--- OCR 文本�?00�?---')
print(resume_text[:800])
print('--- OCR 文本结束 ---')
print(f'text_len = {text_len}')
print(f'text_len >= 4000 ? {text_len >= 4000}')
print('>>> 调用 AI 匹配...')
jd_text = '请根据数学竞赛教练岗位描述进行匹配评�?
try:
    scored_df = ai_match_resumes_df(jd_text, df, job_title='数学竞赛教练')
    first = scored_df.iloc[0]
    print('short_eval:', first.get('short_eval'))
    print('justification(证据):', first.get('证据'))
except Exception as e:
    print('AI 匹配失败:', e)
    import traceback
    traceback.print_exc()
